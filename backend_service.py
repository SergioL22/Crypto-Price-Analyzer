"""Blocking backend orchestration with bounded per-process admission."""
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import BoundedSemaphore

import pandas as pd
from pydantic import ValidationError

import analysis
import api
from backend_models import Evidence, Market, PricesResponse, BacktestResponse
from history_window import select_daily_window
from llm import OpenAIRecommender
from price_validation import validate_prices
from recommendations import build_evidence, RecommendationError, validate_recommendation


class BackendError(Exception):
    def __init__(self, status, code, message, coverage=None):
        super().__init__(message)
        self.status, self.code, self.message, self.coverage = status, code, message, coverage


class AdmissionGate:
    """Thread-safe and nonblocking. Limits active work, not requests per second."""
    def __init__(self, capacity):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('Gate capacity must be a positive integer.')
        self._semaphore = BoundedSemaphore(capacity)

    @contextmanager
    def enter(self):
        if not self._semaphore.acquire(blocking=False):
            raise BackendError(429, 'capacity_exceeded', 'Server is busy; retry later.')
        try:
            yield
        finally:
            self._semaphore.release()


class BackendService:
    def __init__(self, *, history_fetcher=None, prices_fetcher=None, recommender_factory=None,
                 now=None, market_capacity=4, recommendation_capacity=1):
        self.history_fetcher = history_fetcher or api.fetch_history
        self.prices_fetcher = prices_fetcher or api.fetch_top10
        self.recommender_factory = recommender_factory or OpenAIRecommender.from_environment
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.market_gate = AdmissionGate(market_capacity)
        self.recommendation_gate = AdmissionGate(recommendation_capacity)

    def _fresh(self, coin_id, days, minimum, current):
        try:
            with self.market_gate.enter():
                history = self.history_fetcher(coin_id, days, persist=False)
        except api.UpstreamError:
            raise BackendError(502, 'market_upstream_failed', 'CoinGecko could not provide history.') from None
        try:
            frame, coverage = select_daily_window(history, days, now=current)
            frame = validate_prices(frame)
        except (ValueError, TypeError, OverflowError):
            raise BackendError(502, 'invalid_market_data', 'CoinGecko returned invalid history.') from None
        if len(frame) < minimum:
            raise BackendError(503, 'insufficient_history', f'At least {minimum} observations are required.', coverage)
        if coverage['latest_observation_age_days'] > 2:
            raise BackendError(503, 'stale_history', 'Latest history is more than two days old.', coverage)
        return frame, coverage

    def prices(self):
        try:
            with self.market_gate.enter():
                raw = self.prices_fetcher()
        except api.UpstreamError:
            raise BackendError(502, 'market_upstream_failed', 'CoinGecko prices are unavailable.') from None
        try:
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise ValueError('Invalid market envelope')
            # Shape public market fields explicitly; missing data remains null.
            markets = [Market.model_validate({key: item[key] for key in Market.model_fields if key in item}) for item in raw]
            return PricesResponse(currency='usd', fetched_at_utc=self.now().isoformat(), markets=markets)
        except (ValidationError, ValueError, TypeError):
            raise BackendError(502, 'invalid_market_data', 'CoinGecko returned invalid prices.') from None

    def evidence(self, coin_id, days, position=None):
        current = self.now()
        frame, _ = self._fresh(coin_id, days, 35, current)
        portfolio = None if position is None else {coin_id: position}
        try:
            evidence = build_evidence(coin_id, frame, days=days, portfolio=portfolio, now=current)
            Evidence.model_validate(evidence)
            return evidence
        except (RecommendationError, ValidationError, ValueError, TypeError, OverflowError):
            raise BackendError(502, 'invalid_market_data', 'History could not produce valid evidence.') from None

    def backtest(self, coin_id, days, strategy):
        frame, coverage = self._fresh(coin_id, days, 30, self.now())
        result = analysis.backtest_dataframe(frame, coin_id, strategy=strategy, days=days)
        count = result['total_trades']
        summary = dict(strategy=strategy, closed_trades=count, winning_trades=result['winning_trades'],
                       losing_trades=result['losing_trades'], win_rate_pct=result['win_rate'] if count else None,
                       average_closed_trade_return_pct=result['avg_return'] if count else None,
                       asset_max_drawdown_pct=result['max_drawdown'], open_position=result['open_position'])
        trades = [{**trade, 'date': pd.Timestamp(trade['date']).isoformat()} for trade in result['trades']]
        limitations = ['Fees and slippage excluded; same-bar fills; open-position P&L excluded.',
                       'Drawdown describes the underlying asset, not strategy equity.',
                       'Closed-trade returns are not total portfolio returns.',
                       'Periods count observations, not calendar days; the current day may be incomplete.']
        if not coverage['complete']:
            limitations.append(f"Requested window is missing {coverage['missing_days']} daily observations.")
        try:
            return BacktestResponse(coin_id=coin_id, currency='usd', window=coverage, summary=summary,
                                    trades=trades, limitations=limitations)
        except ValidationError:
            raise BackendError(502, 'invalid_market_data', 'History could not produce valid backtest metrics.') from None

    def recommend(self, coin_id, days, position=None):
        with self.recommendation_gate.enter():
            evidence = self.evidence(coin_id, days, position)
            model = None
            try:
                provider = self.recommender_factory()
                model = provider.model
                decision = validate_recommendation(provider.recommend(evidence), evidence)
            except RecommendationError:
                return dict(evidence=evidence, model=model, recommendation_status='unavailable',
                            recommendation=None, ai_error={'code': 'ai_unavailable',
                            'message': 'AI is unavailable, unconfigured, or returned no valid assessment. Raw evidence is available.'})
            return dict(evidence=evidence, model=model, recommendation_status='completed',
                        recommendation=decision, ai_error=None)
