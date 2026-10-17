"""Blocking backend orchestration with bounded per-process admission."""
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import BoundedSemaphore

import pandas as pd
from pydantic import ValidationError

from coin_catalog import CoinCatalog
from stock_service import StockService
from stock_provider import StockDataError
from assets import crypto_asset
import analysis
import api
import portfolio_view
from portfolio_store import PortfolioStore, PortfolioConflict
from alert_store import AlertStore, AlertConflict
import sqlite3
from backend_models import AlertCreate
from backend_models import PortfolioResponse
from backend_models import Evidence, AnalysisResponse, Market, PricesResponse, BacktestResponse
from history_window import select_daily_window
from llm import OpenAIRecommender
from price_validation import validate_prices
from recommendations import build_evidence, RecommendationError, validate_recommendation


class BackendError(Exception):
    def __init__(self, status, code, message, coverage=None, retry_after_seconds=None):
        super().__init__(message)
        self.status, self.code, self.message, self.coverage = status, code, message, coverage
        self.retry_after_seconds=retry_after_seconds


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
                 now=None, market_capacity=4, recommendation_capacity=1, catalog=None,
                 portfolio_loader=None, portfolio_prices_fetcher=None, portfolio_store=None, alert_store=None, stocks=None):
        self.stocks = stocks or StockService()
        self.alert_store = alert_store or AlertStore()
        self.alert_gate = AdmissionGate(1)
        self.portfolio_store = portfolio_store or PortfolioStore()
        self.portfolio_loader = portfolio_loader or portfolio_view.load_saved_portfolio
        self.portfolio_prices_fetcher = portfolio_prices_fetcher or api.fetch_portfolio_prices
        self.catalog = catalog or CoinCatalog()
        self.history_fetcher = history_fetcher or api.fetch_history
        self.prices_fetcher = prices_fetcher or api.fetch_top10
        self.recommender_factory = recommender_factory or OpenAIRecommender.from_environment
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.market_gate = AdmissionGate(market_capacity)
        self.recommendation_gate = AdmissionGate(recommendation_capacity)

    def asset_catalog(self, asset_class):
        if asset_class == 'crypto':
            result = self.coins()
            return dict(assets=[crypto_asset(coin).public() for coin in result['coins']],
                        stale=result['stale'], fetched_at_utc=result['fetched_at_utc'], coverage='CoinGecko crypto catalog; symbols use provider IDs.')
        try:
            with self.market_gate.enter():
                result = self.stocks.catalog(self.now())
            return dict(result, assets=[a for a in result['assets'] if a['asset_class'] == asset_class])
        except StockDataError as error:
            raise BackendError(503, error.code, str(error)) from None

    def stock_research(self, asset_id, days,*,refresh=False):
        try:
            with self.market_gate.enter():
                return self.stocks.research(asset_id, days, self.now(),use_cache=True,refresh=refresh)
        except StockDataError as error:
            raise BackendError(404 if error.code == 'stock_not_found' else 429 if error.code == 'stock_budget' else 503,error.code,str(error),retry_after_seconds=error.retry_after_seconds) from None

    def alerts(self, body=None, *, alert_id=None, active=None):
        try:
            if alert_id is not None:
                return self.alert_store.change(alert_id, active)
            if body is not None:
                return self.alert_store.create(body)
            return self.alert_store.listing()
        except (sqlite3.Error, OSError):
            raise BackendError(503, 'alerts_unavailable', 'Local alerts could not be loaded or saved.') from None
        except AlertConflict as error:
            raise BackendError(409, 'alert_conflict', str(error)) from None

    def check_alerts(self):
        with self.alert_gate.enter():
            saved = self.alerts()
            active = [row for row in saved['alerts'] if row['is_active']]
            if len(active) > 20:
                raise BackendError(409, 'alert_limit', 'Pause alerts until no more than 20 are active.')
            results, quotes, rsi_values = [], {}, {}
            valid = []
            for row in active:
                try:
                    AlertCreate.model_validate({key: row[key] for key in ('coin_id','alert_type','threshold','direction')})
                    valid.append(row)
                except (ValueError, TypeError):
                    results.append(dict(id=row['id'], status='unavailable', message='Saved rule is invalid. Remove it and create a valid rule.'))
            ids = sorted({row['coin_id'] for row in valid if row['alert_type'] == 'price'})
            if ids:
                try:
                    with self.market_gate.enter():
                        quotes = self.portfolio_prices_fetcher(ids)
                except (api.UpstreamError, ValueError):
                    pass
            for row in valid:
                coin = row['coin_id']
                try:
                    if row['alert_type'] == 'price':
                        holding = dict(coin_id=coin, amount=1, average_buy_price_usd=None, cost_basis_usd=None)
                        priced = portfolio_view.snapshot([holding], quotes, self.now())['holdings'][0]
                        if priced['price_status'] != 'current':
                            raise ValueError('Missing recent quote')
                        value, observed = priced['price_usd'], priced['price_updated_at_utc']
                    else:
                        if coin not in rsi_values:
                            try:
                                frame, coverage = self._fresh(coin, 90, 35, self.now())
                                if not coverage['complete']:
                                    raise ValueError('Incomplete RSI history')
                                rsi_values[coin] = (analysis.compute_rsi(frame['price']), frame.index[-1].isoformat())
                            except (BackendError, ValueError, TypeError):
                                rsi_values[coin] = None
                        if rsi_values[coin] is None:
                            raise ValueError('No valid RSI')
                        value, observed = rsi_values[coin]
                        value = portfolio_view.number(value)
                        if value > 100:
                            raise ValueError('Invalid RSI')
                    status = self.alert_store.record(row, value, self.now().isoformat(), observed)
                    results.append(dict(id=row['id'], status=status, value=value, observed_at=observed))
                except (BackendError, ValueError, TypeError, OverflowError):
                    results.append(dict(id=row['id'], status='unavailable', message='Recent valid market data unavailable; previous trigger state was preserved.'))
                except (sqlite3.Error, OSError):
                    raise BackendError(503, 'alerts_unavailable', 'Alert history could not be saved. Reload before checking again.') from None
            return {**self.alerts(), 'results': results}

    def restore_holdings(self, body, *, preview=False):
        try:
            if preview:
                return self.portfolio_store.preview_restore(body.content)
            return self.portfolio_store.restore(body.content, body.version)
        except PortfolioConflict:
            raise BackendError(409, 'portfolio_conflict', 'Holdings changed. Preview the backup again.') from None
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            raise BackendError(422, 'invalid_backup', 'Backup or saved portfolio is invalid, too large, or unavailable. No restore was confirmed.') from None

    def export_holdings(self):
        try:
            return self.portfolio_store.export()
        except (OSError, ValueError, TypeError, OverflowError):
            raise BackendError(503, 'portfolio_unavailable', 'Could not export saved holdings. Check the portfolio file.') from None

    def saved_holdings(self, update=None, *, remove=False):
        try:
            if update is None:
                return self.portfolio_store.read()
            if remove:
                return self.portfolio_store.remove(update.coin_id, update.version)
            return self.portfolio_store.update(update.coin_id, update.amount, update.avg_buy_price, update.version)
        except PortfolioConflict:
            raise BackendError(409, 'portfolio_conflict', 'Holdings changed. Reload the editor before saving again.') from None
        except (OSError, ValueError, TypeError, OverflowError):
            raise BackendError(503, 'portfolio_unavailable', 'Could not read or save holdings. Check the portfolio file and reload.') from None

    def portfolio(self):
        with self.market_gate.enter():
            try:
                holdings = portfolio_view.positions(self.portfolio_loader())
            except (OSError, ValueError, TypeError, OverflowError):
                raise BackendError(503, 'portfolio_unavailable', 'Saved holdings could not be read. Check portfolio.json in the project folder.') from None
            quotes = {}
            if holdings:
                try:
                    quotes = self.portfolio_prices_fetcher([row['coin_id'] for row in holdings])
                except (api.UpstreamError, ValueError):
                    # Preserve holdings while clearly withholding unavailable valuations.
                    pass
            try:
                return PortfolioResponse.model_validate(portfolio_view.snapshot(holdings, quotes, self.now()))
            except (ValueError, OverflowError):
                raise BackendError(503, 'portfolio_unavailable', 'Portfolio values could not be calculated safely.') from None

    def coins(self):
        try:
            return self.catalog.get()
        except api.UpstreamError:
            raise BackendError(503, 'catalog_unavailable', 'Coin list unavailable. Use a quick choice or enter a CoinGecko ID.') from None

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

    def evidence(self, coin_id, days, position=None, *, include_history=False):
        current = self.now()
        frame, _ = self._fresh(coin_id, days, 35, current)
        portfolio = None if position is None else {coin_id: position}
        try:
            evidence = build_evidence(coin_id, frame, days=days, portfolio=portfolio, now=current)
            Evidence.model_validate(evidence)
            if include_history:
                prices = frame['price']
                mid, upper, lower = analysis.compute_bollinger_bands(prices)
                series = dict(price=prices, ma_7=prices.rolling(7).mean(),
                              ma_25=prices.rolling(25).mean(), bollinger_lower=lower,
                              bollinger_middle=mid, bollinger_upper=upper)
                evidence['history'] = [dict(date=pd.Timestamp(date).date().isoformat(),
                    **{key: None if pd.isna(values.iloc[index]) else float(values.iloc[index])
                       for key, values in series.items()}) for index, date in enumerate(frame.index)]
                AnalysisResponse.model_validate(evidence)
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
