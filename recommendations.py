"""Build auditable recommendation evidence without network or terminal access."""
from numbers import Integral
from datetime import datetime, timezone
import json

import pandas as pd

import analysis
from price_validation import finite_number, PriceValidationError
from history_window import select_daily_window


class RecommendationError(RuntimeError):
    """An unavailable or invalid recommendation, safe to display to the user."""


def _number(value, label, *, positive=False):
    try:
        return finite_number(value, label, positive=positive)
    except PriceValidationError as error:
        raise RecommendationError(str(error)) from None


def build_evidence(coin_id, history, *, days=90, portfolio=None, live_price=None, now=None):
    """Use only the supplied fresh window for indicators and backtest calculations.

    Accepts CoinGecko's date column or a DatetimeIndex. Returns plain JSON values.
    Only the selected coin's position is included from the optional portfolio.
    """
    if not isinstance(coin_id, str) or not coin_id.strip() or len(coin_id) > 100:
        raise RecommendationError('A valid CoinGecko coin ID is required.')
    if (not isinstance(days, Integral) or isinstance(days, bool)) or not 35 <= days <= 365:
        raise RecommendationError('The recommendation window must be 35 to 365 days.')
    days = int(days)
    if not isinstance(history, pd.DataFrame) or 'price' not in history:
        raise RecommendationError('Historical prices are missing.')
    current = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
    current = current.tz_localize('UTC') if current.tzinfo is None else current.tz_convert('UTC')
    try:
        frame, coverage = select_daily_window(history, days, now=current)
    except ValueError as error:
        raise RecommendationError(str(error)) from None
    if len(frame) < 35:
        raise RecommendationError('At least 35 daily prices within the requested window are required.')
    age_days = coverage['latest_observation_age_days']
    if age_days > 2:
        raise RecommendationError('Historical prices are more than two days old; refresh before requesting AI advice.')
    frame['price'] = [_number(v, 'Historical price', positive=True) for v in frame['price']]
    warnings = []
    if 'volume' in frame:
        clean_volume = []
        for value in frame['volume']:
            if pd.isna(value):
                clean_volume.append(float('nan'))
                continue
            volume = _number(value, 'Volume')
            if volume < 0:
                raise RecommendationError('Volume cannot be negative.')
            clean_volume.append(volume)
        frame['volume'] = clean_volume
    prices = frame['price']
    mid, upper, lower = analysis.compute_bollinger_bands(prices)
    macd, signal, histogram = analysis.compute_macd(prices)
    support, resistance = analysis.find_support_resistance(prices)
    spikes, avg_volume = analysis.analyze_volume(frame)
    backtest = analysis.backtest_dataframe(frame, coin_id, days=days)
    completed = backtest['total_trades']
    latest = float(prices.iloc[-1])
    valuation_price = latest if live_price is None else _number(live_price, 'Live price', positive=True)
    if coverage['missing_days']:
        warnings.append(f"Requested window is missing {coverage['missing_days']} dates: "
                        f"{coverage['leading_missing_days']} at the start, "
                        f"{coverage['internal_missing_days']} internally, "
                        f"{coverage['trailing_missing_days']} at the end. "
                        "Indicator periods count available observations, not calendar days.")
    if completed < 5:
        warnings.append('Fewer than five closed backtest trades; performance evidence is weak.')
    warnings.extend([
        'Backtest excludes fees and slippage, uses same-bar fills, and omits open-position P&L.',
        'Drawdown is for the underlying asset, not strategy equity; trade returns are not portfolio returns.',
        'Patterns use reversal-confirmed pivots, but do not require neckline breakouts; recent bars may be incomplete.',
        'Support/resistance lists are historical swing lows/highs, not filtered relative to current price; broken levels are not automatically reclassified.',
        'No news, order-book data, investment horizon, or risk tolerance is provided.',
    ])
    position = {'included': portfolio is not None}
    if portfolio is not None:
        if not isinstance(portfolio, dict):
            raise RecommendationError('Portfolio must be a mapping of coin IDs to holdings.')
        holding = portfolio.get(coin_id, {})
        if not isinstance(holding, dict):
            raise RecommendationError('The selected portfolio holding is invalid.')
        amount = _number(holding.get('amount', 0), 'Holding amount')
        cost = _number(holding.get('avg_buy_price', 0), 'Average buy price')
        if amount < 0 or cost < 0:
            raise RecommendationError('Holding amount and average buy price cannot be negative.')
        position.update(amount=amount, average_buy_price_usd=cost if cost > 0 else None,
                        valuation_price_usd=valuation_price, value_usd=amount * valuation_price,
                        unrealized_pnl_usd=amount * (valuation_price - cost) if cost > 0 else None,
                        scope='Selected coin only; total portfolio value and concentration are unknown.')
    volume_available = 'volume' in frame and frame['volume'].notna().any()
    evidence = {
        'coin_id': coin_id, 'currency': 'usd', 'generated_at_utc': current.isoformat(),
        'window': coverage,
        'indicators': {'latest_history_price_usd': latest, 'live_price_usd': None if live_price is None else valuation_price,
                       'rsi_14': analysis.compute_rsi(prices), 'ma_7': float(prices.tail(7).mean()),
                       'ma_25': float(prices.tail(25).mean()), 'macd': float(macd.iloc[-1]),
                       'macd_signal': float(signal.iloc[-1]), 'macd_histogram': float(histogram.iloc[-1]),
                       'bollinger_lower': float(lower.iloc[-1]), 'bollinger_middle': float(mid.iloc[-1]),
                       'bollinger_upper': float(upper.iloc[-1]), 'support': support, 'resistance': resistance,
                       'patterns': analysis.describe_patterns(prices),
                       'average_volume_20': float(avg_volume) if volume_available and pd.notna(avg_volume) else None,
                       'volume_spikes': spikes},
        'backtest': {'strategy': 'rsi_ma', 'closed_trades': completed,
                     'winning_trades': backtest['winning_trades'], 'losing_trades': backtest['losing_trades'],
                     'win_rate_pct': backtest['win_rate'] if completed else None,
                     'average_closed_trade_return_pct': backtest['avg_return'] if completed else None,
                     'asset_max_drawdown_pct': backtest['max_drawdown'],
                     'open_position': backtest['open_position']},
        'portfolio': position, 'limitations': warnings,
    }
    try:
        json.dumps(evidence, allow_nan=False)
    except (ValueError, TypeError):
        raise RecommendationError('Computed evidence contains invalid numeric values.') from None
    return evidence


def evidence_fields(evidence, prefix=''):
    """Flatten evidence paths for the terminal and validated model references."""
    fields = {}
    for key, value in evidence.items():
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(value, dict):
            fields.update(evidence_fields(value, path))
        else:
            fields[path] = value
    return fields


def validate_recommendation(value, evidence):
    """Reject malformed decisions and citations to nonexistent evidence."""
    required = {'action', 'confidence', 'confidence_explanation', 'summary', 'reasons', 'risks'}
    if not isinstance(value, dict) or set(value) != required:
        raise RecommendationError('AI returned an invalid recommendation structure.')
    if value['action'] not in ('BUY', 'HOLD', 'SELL'):
        raise RecommendationError('AI returned an invalid action.')
    if value['confidence'] not in ('low', 'medium', 'high'):
        raise RecommendationError('AI returned an invalid confidence level.')
    def valid_text(text):
        return (isinstance(text, str) and 0 < len(text.strip()) <= 1200
                and not any(ord(c) < 32 and c not in '\n\t' or ord(c) == 127 for c in text))
    if not all(valid_text(value[k]) for k in ('summary', 'confidence_explanation')):
        raise RecommendationError('AI returned invalid explanatory text.')
    fields = evidence_fields(evidence)
    for category in ('reasons', 'risks'):
        items = value[category]
        if not isinstance(items, list) or not 1 <= len(items) <= 6:
            raise RecommendationError(f'AI must provide one to six evidence-linked {category}.')
        for item in items:
            if not isinstance(item, dict) or set(item) != {'evidence_keys', 'explanation'}:
                raise RecommendationError(f'AI returned invalid {category}.')
            keys = item['evidence_keys']
            if (not isinstance(keys, list) or not 1 <= len(keys) <= 12
                    or not all(isinstance(key, str) and key in fields for key in keys)
                    or len(set(keys)) != len(keys) or not valid_text(item['explanation'])):
                raise RecommendationError(f'AI cited unknown evidence or returned invalid {category}.')
    return value
