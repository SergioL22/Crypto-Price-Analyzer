"""Technical indicators and backtests, independent of terminal and chart libraries."""
from numbers import Integral
import pandas as pd
import api
import data
from history_window import select_daily_window


def compute_rsi_series(prices: pd.Series, period: int = 14) -> pd.Series:
    """Causal Wilder RSI: seed with period-average gains/losses, then smooth.

    Warm-up observations are NaN. Each later value uses only that observation
    and earlier prices, so this same series can drive a backtest without lookahead.
    """
    if (not isinstance(period, Integral) or isinstance(period, bool)) or period < 1:
        raise ValueError("RSI period must be a positive integer")
    period = int(period)
    result = pd.Series(float('nan'), index=prices.index, dtype=float, name='rsi')
    if len(prices) <= period:
        return result
    delta = prices.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = float(gains.iloc[1:period+1].mean())
    avg_loss = float(losses.iloc[1:period+1].mean())
    for i in range(period, len(prices)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains.iloc[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses.iloc[i]) / period
        if avg_loss == 0:
            result.iloc[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            result.iloc[i] = 100 - 100 / (1 + avg_gain / avg_loss)
    return result


def compute_rsi(prices: pd.Series, period: int = 14) -> float:
    """Latest Wilder RSI; retain a neutral 50 for insufficient history."""
    values = compute_rsi_series(prices, period)
    if values.empty or pd.isna(values.iloc[-1]):
        return 50.0
    return float(values.iloc[-1])


def compute_ema(prices: pd.Series, span: int) -> pd.Series:
    return prices.ewm(span=span, adjust=False).mean()


def compute_macd(prices: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast_ema = compute_ema(prices, 12)
    slow_ema = compute_ema(prices, 26)
    macd = fast_ema - slow_ema
    signal_line = compute_ema(macd, 9)
    histogram = macd - signal_line
    return macd, signal_line, histogram


def compute_bollinger_bands(prices: pd.Series, window: int = 20, num_std: int = 2) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower


def _zigzag_extrema(prices: pd.Series, threshold_pct: float = 3.0) -> tuple[pd.Series, pd.Series]:
    """Find significant local peaks and troughs (a "zigzag" filter).

    The previous approach called any point higher than its immediate left and
    right neighbor a "peak" -- on daily closes that fires on nearly every
    up-down wiggle, making pattern detection mostly noise. This only records a
    turning point once price has moved at least threshold_pct% away from the
    prior extreme, which is a standard way to separate real swings from
    day-to-day chop.
    """
    if len(prices) < 3:
        empty = prices.iloc[0:0]
        return empty, empty

    values = prices.to_numpy()
    pivots: list[tuple[int, str]] = []
    trend = 0  # 0 = undetermined, 1 = rising, -1 = falling
    extreme_pos = 0
    extreme_val = values[0]

    for i in range(1, len(values)):
        v = values[i]
        if trend >= 0 and v >= extreme_val:
            extreme_val, extreme_pos, trend = v, i, 1
            continue
        if trend <= 0 and v <= extreme_val:
            extreme_val, extreme_pos, trend = v, i, -1
            continue

        change_pct = abs(v - extreme_val) / extreme_val * 100
        if change_pct >= threshold_pct:
            pivots.append((extreme_pos, 'peak' if trend == 1 else 'trough'))
            trend = -trend
            extreme_val, extreme_pos = v, i

    # The trailing extreme has no subsequent threshold reversal yet. Never
    # promote it to a confirmed pivot, even if earlier swings were confirmed.
    peak_positions = sorted({pos for pos, kind in pivots if kind == 'peak'})
    trough_positions = sorted({pos for pos, kind in pivots if kind == 'trough'})
    return prices.iloc[peak_positions], prices.iloc[trough_positions]


def find_support_resistance(prices: pd.Series, threshold_pct: float = 3.0, top_n: int = 3) -> tuple[list[float], list[float]]:
    peaks, troughs = _zigzag_extrema(prices, threshold_pct)
    resistance = peaks.nlargest(top_n).tolist()
    support = troughs.nsmallest(top_n).tolist()
    return support, resistance


def detect_head_and_shoulders(prices: pd.Series, threshold_pct: float = 3.0) -> bool:
    peaks, _ = _zigzag_extrema(prices, threshold_pct)
    if len(peaks) < 3:
        return False
    for i in range(len(peaks) - 2):
        left, head, right = peaks.iloc[i:i+3]
        if head > left and head > right and abs(left - right) / head < 0.15:
            return True
    return False


def detect_double_top_bottom(prices: pd.Series, threshold_pct: float = 3.0) -> tuple[bool, bool]:
    peaks, troughs = _zigzag_extrema(prices, threshold_pct)
    double_top = False
    double_bottom = False
    if len(peaks) >= 2:
        first, second = peaks.iloc[-2:]
        if abs(first - second) / ((first + second) / 2) < 0.06:
            double_top = True
    if len(troughs) >= 2:
        first, second = troughs.iloc[-2:]
        if abs(first - second) / ((first + second) / 2) < 0.06:
            double_bottom = True
    return double_top, double_bottom


def analyze_volume(df: pd.DataFrame) -> tuple[list[str], float]:
    if "volume" not in df or df["volume"].isna().all():
        return [], 0.0

    avg_volume = df["volume"].rolling(20, min_periods=5).mean()
    spike_mask = df["volume"] > avg_volume * 1.5
    prev_prices = df["price"].shift(1)
    volume_spikes = []
    for date, row in df[spike_mask].tail(3).iterrows():
        prev = prev_prices.loc[date]
        pct = (row["price"] / prev - 1) if pd.notna(prev) and prev != 0 else 0.0
        label = "up" if pct >= 0 else "down"
        volume_spikes.append(f"{date}: {label} move on high volume")
    latest_avg = avg_volume.iloc[-1] if not avg_volume.empty else 0.0
    return volume_spikes, latest_avg


def describe_patterns(prices: pd.Series) -> list[str]:
    patterns = []
    if detect_head_and_shoulders(prices):
        patterns.append("Possible Head & Shoulders")
    double_top, double_bottom = detect_double_top_bottom(prices)
    if double_top:
        patterns.append("Possible Double Top")
    if double_bottom:
        patterns.append("Possible Double Bottom")
    if not patterns:
        patterns.append("No clear pattern detected")
    return patterns


def backtest_strategy(coin_id: str, strategy: str, days: int = 90) -> dict:
    """Backtest a trading strategy against historical data.

    Always fetches fresh history for the requested period first. Previously
    this only read whatever happened to already be cached locally, so the
    same backtest could silently run on a much shorter window than requested
    (or fail outright) depending on unrelated earlier menu use.
    """
    if strategy != 'rsi_ma':
        return {"error": f"Unsupported strategy: {strategy}"}
    if (not isinstance(days, Integral) or isinstance(days, bool)) or not 30 <= days <= 365:
        return {"error": "Backtest window must be 30 to 365 days."}
    days = int(days)
    try:
        fresh = api.fetch_history(coin_id, days)
        df, coverage = select_daily_window(fresh, days)
    except (RuntimeError, ValueError) as error:
        return {"error": f"Could not prepare fresh history: {error}"}

    result = backtest_dataframe(df, coin_id, strategy, days)
    if 'error' not in result:
        result['window'] = coverage
        data.save_backtest_result(result)
    return result


def backtest_dataframe(df: pd.DataFrame, coin_id: str, strategy: str = 'rsi_ma', days: int = 90) -> dict:
    """Calculate a backtest without network, database, or terminal access.

    ``days`` labels the supplied window; callers provide the appropriate rows.
    Max drawdown describes the underlying price series, as in the CLI strategy.
    """
    if strategy != 'rsi_ma':
        return {"error": f"Unsupported strategy: {strategy}"}
    if df is None or len(df) < 30:
        return {"error": "Insufficient historical data"}

    prices = df['price']
    rsi_values = compute_rsi_series(prices)
    ma7_values = prices.rolling(7).mean()
    trades = []
    position = 0  # 0 = no position, 1 = long
    entry_price = 0

    if strategy == 'rsi_ma':
        for i in range(25, len(prices)):
            rsi = rsi_values.iloc[i]
            ma7 = ma7_values.iloc[i]

            if rsi < 30 and prices.iloc[i] > ma7 and position == 0:
                position = 1
                entry_price = prices.iloc[i]
                trades.append({'type': 'BUY', 'price': entry_price, 'date': df.index[i]})
            elif rsi > 70 and position == 1:
                exit_price = prices.iloc[i]
                pnl = (exit_price - entry_price) / entry_price * 100
                trades.append({'type': 'SELL', 'price': exit_price, 'date': df.index[i], 'pnl': pnl})
                position = 0


    # Calculate metrics
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

    total_trades = len([t for t in trades if t['type'] == 'SELL'])
    win_rate = len(winning_trades) / max(total_trades, 1) * 100
    avg_return = sum(t.get('pnl', 0) for t in trades if 'pnl' in t) / max(total_trades, 1)

    # Calculate max drawdown
    cumulative = (1 + prices.pct_change()).cumprod()
    peak = cumulative.expanding().max()
    drawdown = (cumulative - peak) / peak
    max_drawdown = drawdown.min() * 100

    result = {
        'coin_id': coin_id,
        'strategy': strategy,
        'period_days': days,  # Requested window, not a claim of available coverage.
        'observations': len(df),
        'start_date': str(df.index[0]),
        'end_date': str(df.index[-1]),
        'open_position': bool(position),
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'avg_return': avg_return,
        'max_drawdown': max_drawdown,
        'trades': trades
    }

    return result

