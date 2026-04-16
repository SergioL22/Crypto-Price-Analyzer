#!/usr/bin/env python3
"""Project 6 Cryptocurrency Price Analysis

Features
  1. Live prices for top 10 cryptos by market cap
  2. Historical price analysis (7d + 30d)
  3. Trading signals (RSI + Moving Averages)
  4. Portfolio tracker (holdings  current value + P&L)

Data source: CoinGecko public API (no key required)
"""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Optional

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import plotly.graph_objects as go
import requests
from colorama import Fore, Style, init
from tabulate import tabulate

init(autoreset=True)

BASE_URL = "https://api.coingecko.com/api/v3/"
CURRENCY = "usd"
TOP_N = 10
PORTFOLIO_FILE = "portfolio.json"
ALERTS_LOG_FILE = "alerts.log"
DB_FILE = "crypto_data.db"


# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────
def init_database() -> None:
    """Initialize SQLite database for data persistence."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create price history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY,
            coin_id TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL NOT NULL,
            volume REAL,
            market_cap REAL,
            timestamp INTEGER,
            UNIQUE(coin_id, date)
        )
    ''')

    # Create alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            coin_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            threshold REAL NOT NULL,
            direction TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_triggered TEXT
        )
    ''')

    # Create backtest results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY,
            coin_id TEXT NOT NULL,
            strategy TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            total_trades INTEGER,
            winning_trades INTEGER,
            losing_trades INTEGER,
            win_rate REAL,
            avg_return REAL,
            max_drawdown REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def save_price_data(coin_id: str, df: pd.DataFrame) -> None:
    """Save price data to database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO price_history
            (coin_id, date, price, volume, market_cap, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            coin_id,
            row['date'].isoformat(),
            row['price'],
            row.get('volume'),
            None,  # market_cap not available in current data
            int(pd.Timestamp(row['date']).timestamp())
        ))

    conn.commit()
    conn.close()


def load_price_data(coin_id: str, days: int = 30) -> Optional[pd.DataFrame]:
    """Load price data from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cutoff_date = datetime.now() - pd.Timedelta(days=days)

    cursor.execute('''
        SELECT date, price, volume FROM price_history
        WHERE coin_id = ? AND date >= ?
        ORDER BY date ASC
    ''', (coin_id, cutoff_date.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=['date', 'price', 'volume'])
    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date')


def log_alert(coin_id: str, alert_type: str, message: str) -> None:
    """Log alert to file and console."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {coin_id.upper()}: {alert_type} - {message}"

    # Print to console with color
    print(Fore.YELLOW + f"🚨 ALERT: {log_message}")

    # Write to log file
    with open(ALERTS_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_message + '\n')


def save_alert(coin_id: str, alert_type: str, threshold: float, direction: str) -> None:
    """Save alert configuration to database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO alerts (coin_id, alert_type, threshold, direction)
        VALUES (?, ?, ?, ?)
    ''', (coin_id, alert_type, threshold, direction))

    conn.commit()
    conn.close()


def load_alerts() -> list[dict]:
    """Load active alerts from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM alerts WHERE is_active = 1')
    rows = cursor.fetchall()
    conn.close()

    alerts = []
    for row in rows:
        alerts.append({
            'id': row[0],
            'coin_id': row[1],
            'alert_type': row[2],
            'threshold': row[3],
            'direction': row[4],
            'is_active': row[5],
            'created_at': row[6],
            'last_triggered': row[7]
        })
    return alerts


def check_alerts(coins: list[dict]) -> None:
    """Check all active alerts against current data."""
    alerts = load_alerts()
    if not alerts:
        return

    price_map = {coin['id']: coin['current_price'] for coin in coins}

    for alert in alerts:
        coin_id = alert['coin_id']
        alert_type = alert['alert_type']
        threshold = alert['threshold']
        direction = alert['direction']

        if coin_id not in price_map:
            continue

        current_price = price_map[coin_id]

        if alert_type == 'price':
            if direction == 'above' and current_price > threshold:
                log_alert(coin_id, 'PRICE ALERT', f"Price ${current_price:.2f} broke above ${threshold:.2f}")
                # Mark as triggered
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute('UPDATE alerts SET last_triggered = ? WHERE id = ?',
                             (datetime.now().isoformat(), alert['id']))
                conn.commit()
                conn.close()

            elif direction == 'below' and current_price < threshold:
                log_alert(coin_id, 'PRICE ALERT', f"Price ${current_price:.2f} broke below ${threshold:.2f}")
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute('UPDATE alerts SET last_triggered = ? WHERE id = ?',
                             (datetime.now().isoformat(), alert['id']))
                conn.commit()
                conn.close()

        elif alert_type == 'rsi':
            # Need to calculate RSI for this coin
            try:
                df = fetch_history(coin_id, 30)
                if len(df) >= 15:
                    rsi = compute_rsi(df['price'])
                    if direction == 'above' and rsi > threshold:
                        log_alert(coin_id, 'RSI ALERT', f"RSI {rsi:.1f} crossed above {threshold}")
                    elif direction == 'below' and rsi < threshold:
                        log_alert(coin_id, 'RSI ALERT', f"RSI {rsi:.1f} crossed below {threshold}")
            except:
                pass  # Skip if can't fetch data


def backtest_strategy(coin_id: str, strategy: str, days: int = 90) -> dict:
    """Backtest a trading strategy against historical data."""
    df = load_price_data(coin_id, days)
    if df is None or len(df) < 30:
        return {"error": "Insufficient historical data"}

    prices = df['price']
    signals = []
    trades = []
    position = 0  # 0 = no position, 1 = long
    entry_price = 0

    if strategy == 'rsi_ma':
        for i in range(25, len(prices)):
            window = prices.iloc[i-25:i+1]
            rsi = compute_rsi(window)
            ma7 = window.tail(7).mean()
            ma25 = window.tail(25).mean()

            signal = None
            if rsi < 30 and prices.iloc[i] > ma7 and position == 0:
                signal = 'BUY'
                position = 1
                entry_price = prices.iloc[i]
                trades.append({'type': 'BUY', 'price': entry_price, 'date': df.index[i]})
            elif rsi > 70 and position == 1:
                signal = 'SELL'
                exit_price = prices.iloc[i]
                pnl = (exit_price - entry_price) / entry_price * 100
                trades.append({'type': 'SELL', 'price': exit_price, 'date': df.index[i], 'pnl': pnl})
                position = 0

            signals.append(signal)

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
        'period_days': days,
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'avg_return': avg_return,
        'max_drawdown': max_drawdown,
        'trades': trades
    }

    # Save to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO backtest_results
        (coin_id, strategy, period_days, total_trades, winning_trades, losing_trades,
         win_rate, avg_return, max_drawdown)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        coin_id, strategy, days, total_trades, len(winning_trades), len(losing_trades),
        win_rate, avg_return, max_drawdown
    ))
    conn.commit()
    conn.close()

    return result


def plot_price_chart(coin_id: str, days: int = 30, save_path: Optional[str] = None) -> None:
    """Create and display/save a price chart with technical indicators."""
    df = load_price_data(coin_id, days)
    if df is None or len(df) < 20:
        print(Fore.RED + "Insufficient data for charting.")
        return

    prices = df['price']

    # Calculate indicators
    ma7 = prices.rolling(7).mean()
    ma25 = prices.rolling(25).mean()
    bb_mid, bb_upper, bb_lower = compute_bollinger_bands(prices)

    # Create plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})

    # Price chart
    ax1.plot(df.index, prices, label='Price', color='blue', linewidth=1)
    ax1.plot(df.index, ma7, label='MA7', color='orange', linewidth=1)
    ax1.plot(df.index, ma25, label='MA25', color='red', linewidth=1)
    ax1.fill_between(df.index, bb_lower, bb_upper, alpha=0.2, color='gray', label='Bollinger Bands')
    ax1.set_title(f'{coin_id.upper()} Price Chart ({days} days)')
    ax1.set_ylabel('Price (USD)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Volume chart
    if 'volume' in df.columns and df['volume'].notna().any():
        ax2.bar(df.index, df['volume'], color='green', alpha=0.7)
        ax2.set_ylabel('Volume')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(Fore.GREEN + f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def plot_candlestick_chart(coin_id: str, days: int = 30, save_path: Optional[str] = None) -> None:
    """Create and display/save a candlestick chart."""
    df = load_price_data(coin_id, days)
    if df is None or len(df) < 20:
        print(Fore.RED + "Insufficient data for candlestick chart.")
        return

    # Convert to OHLC format (simplified - using daily close as OHLC)
    ohlc_df = df.copy()
    ohlc_df['Open'] = ohlc_df['price'].shift(1).fillna(ohlc_df['price'])
    ohlc_df['High'] = ohlc_df[['Open', 'price']].max(axis=1)
    ohlc_df['Low'] = ohlc_df[['Open', 'price']].min(axis=1)
    ohlc_df['Close'] = ohlc_df['price']
    ohlc_df['Volume'] = ohlc_df['volume'].fillna(0)
    ohlc_df = ohlc_df[['Open', 'High', 'Low', 'Close', 'Volume']]

    # Create candlestick chart
    fig, ax = mpf.figure(figsize=(12, 8), style='charles')()
    mpf.plot(ohlc_df, type='candle', volume=True, style='charles', ax=ax)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(Fore.GREEN + f"Candlestick chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def plot_interactive_chart(coin_id: str, days: int = 30) -> None:
    """Create an interactive Plotly chart."""
    df = load_price_data(coin_id, days)
    if df is None or len(df) < 20:
        print(Fore.RED + "Insufficient data for interactive chart.")
        return

    prices = df['price']
    ma7 = prices.rolling(7).mean()
    ma25 = prices.rolling(25).mean()

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(x=df.index, y=prices, mode='lines', name='Price',
                            line=dict(color='blue', width=2)))

    # Moving averages
    fig.add_trace(go.Scatter(x=df.index, y=ma7, mode='lines', name='MA7',
                            line=dict(color='orange', width=1)))
    fig.add_trace(go.Scatter(x=df.index, y=ma25, mode='lines', name='MA25',
                            line=dict(color='red', width=1)))

    fig.update_layout(
        title=f'{coin_id.upper()} Interactive Price Chart ({days} days)',
        xaxis_title='Date',
        yaxis_title='Price (USD)',
        hovermode='x unified'
    )

    fig.show()


def _get(endpoint: str, params: dict | None = None) -> dict:
    """Send a GET request to CoinGecko with retry logic."""
    if params is None:
        params = {}

    url = f"{BASE_URL}{endpoint}"
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            if status_code == 429:
                wait = 15 * (attempt + 1)
                print(Fore.YELLOW + f"Rate limited  waiting {wait}s...")
                time.sleep(wait)
                continue
            print(Fore.RED + f"HTTP error: {error}")
            sys.exit(1)
        except requests.exceptions.RequestException as error:
            print(Fore.RED + f"Network error: {error}")
            sys.exit(1)

    print(Fore.RED + "Max retries reached.")
    sys.exit(1)


def _color_pct(value: float) -> str:
    if value is None:
        value = 0.0
    formatted = f"{value:+.2f}%"
    return Fore.GREEN + formatted if value >= 0 else Fore.RED + formatted


def _fmt_price(value: float) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}" if value >= 1 else f"${value:.6f}"


def _fmt_large(value: float) -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def _divider(title: str = "") -> None:
    width = 70
    if title:
        padding = max((width - len(title) - 2) // 2, 0)
        print(Fore.CYAN + "─" * padding + f" {title} " + "─" * padding)
    else:
        print(Fore.CYAN + "─" * width)


def fetch_top10() -> list[dict]:
    """Fetch top 10 coins by market cap."""
    return _get("coins/markets", {
        "vs_currency": CURRENCY,
        "order": "market_cap_desc",
        "per_page": TOP_N,
        "page": 1,
        "price_change_percentage": "1h,24h,7d",
        "sparkline": False,
    })


def show_live_prices(coins: list[dict]) -> None:
    _divider("LIVE PRICES  Top 10 by Market Cap")
    rows = []
    for idx, coin in enumerate(coins, start=1):
        pct_1h = coin.get("price_change_percentage_1h_in_currency") or 0.0
        pct_24h = coin.get("price_change_percentage_24h_in_currency") or 0.0
        pct_7d = coin.get("price_change_percentage_7d_in_currency") or 0.0
        rows.append([
            idx,
            coin.get("symbol", "").upper(),
            coin.get("name", ""),
            _fmt_price(coin.get("current_price", 0.0)),
            _color_pct(pct_1h),
            _color_pct(pct_24h),
            _color_pct(pct_7d),
            _fmt_large(coin.get("market_cap", 0.0)),
            _fmt_large(coin.get("total_volume", 0.0)),
        ])

    headers = ["#", "SYM", "Name", "Price", "1h %", "24h %", "7d %", "Mkt Cap", "Volume 24h"]
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print(Fore.WHITE + Style.DIM + f"Last updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} local\n")


def fetch_history(coin_id: str, days: int) -> pd.DataFrame:
    data = _get(f"coins/{coin_id}/market_chart", {
        "vs_currency": CURRENCY,
        "days": days,
        "interval": "daily",
    })
    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])
    df = pd.DataFrame(prices, columns=["timestamp", "price"])
    if len(volumes) == len(df):
        df["volume"] = [volume[1] for volume in volumes]
    else:
        df["volume"] = None
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.date
    df = df.groupby(["date"])[["price", "volume"]].last().reset_index()

    # Save to database for persistence
    save_price_data(coin_id, df)

    return df


def show_historical(coins: list[dict]) -> None:
    _divider("HISTORICAL ANALYSIS")

    rows_7d = []
    rows_30d = []

    print(Fore.WHITE + "Fetching 30-day history for each coin (may take a moment)...\n")

    for coin in coins:
        cid = coin.get("id")
        sym = coin.get("symbol", "").upper()
        if not cid:
            continue

        try:
            df = fetch_history(cid, 30)
        except Exception as error:
            print(Fore.YELLOW + f"Skipping {sym}: {error}")
            continue

        if len(df) < 2:
            continue

        p_now = df["price"].iloc[-1]
        p_30 = df["price"].iloc[0]
        hi_30 = df["price"].max()
        lo_30 = df["price"].min()
        chg_30 = (p_now - p_30) / p_30 * 100 if p_30 else 0.0
        rows_30d.append([sym, _fmt_price(p_now), _fmt_price(lo_30), _fmt_price(hi_30), _color_pct(chg_30)])

        df7 = df.tail(8)
        p_7 = df7["price"].iloc[0]
        chg_7 = (p_now - p_7) / p_7 * 100 if p_7 else 0.0
        hi_7 = df7["price"].max()
        lo_7 = df7["price"].min()
        rows_7d.append([sym, _fmt_price(p_now), _fmt_price(lo_7), _fmt_price(hi_7), _color_pct(chg_7)])

        time.sleep(0.6)

    print(" 7-Day Summary ")
    print(tabulate(rows_7d, headers=["SYM", "Price Now", "7d Low", "7d High", "7d Change"], tablefmt="simple"))
    print()
    print(" 30-Day Summary ")
    print(tabulate(rows_30d, headers=["SYM", "Price Now", "30d Low", "30d High", "30d Change"], tablefmt="simple"))
    print()


def compute_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 0.0


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


def find_support_resistance(prices: pd.Series, window: int = 5, top_n: int = 3) -> tuple[list[float], list[float]]:
    highs = prices[(prices.shift(1) < prices) & (prices.shift(-1) < prices)]
    lows = prices[(prices.shift(1) > prices) & (prices.shift(-1) > prices)]
    resistance = highs.nlargest(top_n).tolist()
    support = lows.nsmallest(top_n).tolist()
    return support, resistance


def detect_head_and_shoulders(prices: pd.Series) -> bool:
    peaks = prices[(prices.shift(1) < prices) & (prices.shift(-1) < prices)]
    if len(peaks) < 3:
        return False
    for i in range(len(peaks) - 2):
        left, head, right = peaks.iloc[i:i+3]
        if head > left and head > right and abs(left - right) / head < 0.15:
            return True
    return False


def detect_double_top_bottom(prices: pd.Series) -> tuple[bool, bool]:
    peaks = prices[(prices.shift(1) < prices) & (prices.shift(-1) < prices)]
    troughs = prices[(prices.shift(1) > prices) & (prices.shift(-1) > prices)]
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
    volume_spikes = []
    for _, row in df[spike_mask].tail(3).iterrows():
        pct = row["price"] / df["price"].shift(1).loc[_] - 1 if _ in df.index and _ - 1 in df.index else 0.0
        label = "up" if pct >= 0 else "down"
        volume_spikes.append(f"{row['date']}: {label} move on high volume")
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


def signal_label(rsi: float, price: float, ma7: float, ma25: float) -> str:
    if rsi < 30 and price > ma7:
        return Fore.GREEN + " BUY"
    if rsi > 70:
        return Fore.RED + " SELL"
    if ma7 > ma25:
        return Fore.GREEN + " BULLISH"
    if ma7 < ma25:
        return Fore.YELLOW + " BEARISH"
    return Fore.WHITE + " NEUTRAL"


def show_signals(coins: list[dict]) -> None:
    _divider("TRADING SIGNALS (RSI + Moving Averages)")
    print(Fore.WHITE + "Fetching 30-day history for signal calculation...\n")

    rows = []
    for coin in coins:
        cid = coin.get("id")
        sym = coin.get("symbol", "").upper()
        if not cid:
            continue

        try:
            df = fetch_history(cid, 30)
        except Exception:
            continue

        if len(df) < 15:
            continue

        prices = df["price"]
        ma7 = prices.tail(7).mean()
        ma25 = prices.tail(25).mean() if len(prices) >= 25 else prices.mean()
        rsi = compute_rsi(prices)
        current_price = prices.iloc[-1]
        sig = signal_label(rsi, current_price, ma7, ma25)

        rsi_str = f"{rsi:.1f}"
        if rsi < 30:
            rsi_str = Fore.GREEN + rsi_str + " (oversold)"
        elif rsi > 70:
            rsi_str = Fore.RED + rsi_str + " (overbought)"

        rows.append([sym, _fmt_price(current_price), _fmt_price(ma7), _fmt_price(ma25), rsi_str, sig])
        time.sleep(0.6)

    headers = ["SYM", "Price", "MA7", "MA25", "RSI(14)", "Signal"]
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print()
    print(Fore.WHITE + Style.DIM + "Signals are informational only  not financial advice.\n")


def show_technical_analysis(coins: list[dict]) -> None:
    _divider("TECHNICAL ANALYSIS")
    symbol_map = {coin.get("symbol", "").upper(): coin for coin in coins if coin.get("id")}
    print(Fore.WHITE + "Available coins: " + ", ".join(sorted(symbol_map.keys())))
    choice = input("Enter a symbol for technical analysis: ").strip().upper()
    coin = symbol_map.get(choice)
    if coin is None:
        print(Fore.YELLOW + "Symbol not found. Using top coin by default.")
        coin = coins[0]

    cid = coin["id"]
    sym = coin.get("symbol", "").upper()
    print(Fore.WHITE + f"Fetching 60-day history for {sym}...\n")
    try:
        df = fetch_history(cid, 60)
    except Exception as error:
        print(Fore.RED + f"Failed to fetch history for {sym}: {error}")
        return

    if len(df) < 20:
        print(Fore.YELLOW + "Not enough history to perform technical analysis.")
        return

    prices = df["price"]
    volumes = df["volume"] if "volume" in df else pd.Series(dtype=float)

    bb_mid, bb_upper, bb_lower = compute_bollinger_bands(prices)
    macd, signal_line, hist = compute_macd(prices)
    support, resistance = find_support_resistance(prices)
    patterns = describe_patterns(prices)
    volume_spikes, avg_volume = analyze_volume(df)

    latest_price = prices.iloc[-1]
    latest_bb = (bb_lower.iloc[-1], bb_mid.iloc[-1], bb_upper.iloc[-1])
    latest_macd = macd.iloc[-1]
    latest_signal = signal_line.iloc[-1]
    latest_hist = hist.iloc[-1]

    # Create technical analysis table
    rows = [
        ["Latest Price", _fmt_price(latest_price)],
        ["Bollinger Bands (20d)", ""],
        ["  Lower", _fmt_price(latest_bb[0])],
        ["  Middle", _fmt_price(latest_bb[1])],
        ["  Upper", _fmt_price(latest_bb[2])],
        ["MACD", ""],
        ["  MACD Line", f"{latest_macd:.4f}"],
        ["  Signal Line", f"{latest_signal:.4f}"],
        ["  Histogram", f"{latest_hist:.4f}"],
        ["Support Levels", ", ".join(_fmt_price(level) for level in support)],
        ["Resistance Levels", ", ".join(_fmt_price(level) for level in resistance)],
        ["Chart Patterns", ", ".join(patterns)],
        ["Volume Analysis", ""],
        ["  Avg Volume (20d)", f"{int(avg_volume):,}"],
        ["  High-Volume Moves", ""],
    ]

    # Add volume spikes if any
    if volume_spikes:
        for spike in volume_spikes:
            rows.append(["", spike])
    else:
        rows.append(["", "No significant volume spikes detected"])

    headers = [f"{sym} Technical Analysis", "Value"]
    print(tabulate(rows, headers=headers, tablefmt="grid", colalign=("left", "right")))
    print()
    print(Fore.WHITE + Style.DIM + "Technical analysis is informational only — not financial advice.\n")


def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_portfolio(portfolio: dict) -> None:
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as file:
        json.dump(portfolio, file, indent=2)
    print(Fore.GREEN + f"Portfolio saved to {PORTFOLIO_FILE}")


def edit_portfolio(coins: list[dict]) -> None:
    portfolio = load_portfolio()
    id_map = {coin.get("symbol", "").upper(): coin.get("id") for coin in coins if coin.get("id")}

    print(Fore.CYAN + "\nEnter your holdings (leave blank to skip, 0 to remove).")
    print(Fore.CYAN + f"Available: {', '.join(sorted(id_map.keys()))}\n")

    for sym, cid in id_map.items():
        current = portfolio.get(cid, {})
        held = current.get("amount", 0)
        avg = current.get("avg_buy_price", 0)

        raw = input(f"{sym}  amount held [{held}]: ").strip()
        if raw == "":
            continue
        try:
            amount = float(raw)
        except ValueError:
            print(Fore.YELLOW + "Invalid amount, skipping.")
            continue

        if amount == 0:
            portfolio.pop(cid, None)
            print(Fore.YELLOW + f"Removed {sym}.")
            continue

        raw_avg = input(f"{sym}  avg buy price USD [{avg if avg else 'unknown'}]: ").strip()
        try:
            avg_price = float(raw_avg) if raw_avg else float(avg)
        except ValueError:
            avg_price = 0.0

        portfolio[cid] = {"symbol": sym, "amount": amount, "avg_buy_price": avg_price}

    save_portfolio(portfolio)


def show_portfolio(coins: list[dict]) -> None:
    _divider("PORTFOLIO TRACKER")
    portfolio = load_portfolio()

    if not portfolio:
        print(Fore.YELLOW + "No portfolio found. Run option 5  Edit Portfolio first.\n")
        return

    price_map = {coin.get("id"): coin.get("current_price", 0.0) for coin in coins}
    rows = []
    total_value = 0.0
    total_cost = 0.0

    for cid, entry in portfolio.items():
        sym = entry.get("symbol", "")
        amt = float(entry.get("amount", 0.0))
        avg = float(entry.get("avg_buy_price", 0.0))
        price = price_map.get(cid, 0.0)
        value = amt * price
        cost = amt * avg if avg else None
        pnl = value - cost if cost is not None else None
        pnl_pct = (pnl / cost * 100) if cost else None

        total_value += value
        if cost is not None:
            total_cost += cost

        rows.append([
            sym,
            f"{amt:.6f}".rstrip("0").rstrip("."),
            _fmt_price(price),
            _fmt_large(value),
            _fmt_price(avg) if avg else "",
            _color_pct(pnl_pct) if pnl_pct is not None else "",
            (Fore.GREEN + f"${pnl:,.2f}" if pnl is not None and pnl >= 0 else Fore.RED + f"${pnl:,.2f}") if pnl is not None else "",
        ])

    headers = ["SYM", "Amount", "Price", "Value", "Avg Buy", "P&L %", "P&L USD"]
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print()
    print(f"{'Total Portfolio Value':28} {Fore.CYAN}{_fmt_large(total_value)}")
    if total_cost:
        total_pnl = total_value - total_cost
        total_pnl_pct = total_pnl / total_cost * 100
        print(f"{'Total Cost Basis':28} {_fmt_large(total_cost)}")
        print(f"{'Total P&L':28} {_color_pct(total_pnl_pct)}  (${total_pnl:,.2f})")
    print()


def setup_alert(coins: list[dict]) -> None:
    """Set up price or RSI alerts for a coin."""
    _divider("SETUP ALERT")
    symbol_map = {coin.get("symbol", "").upper(): coin for coin in coins if coin.get("id")}
    print(Fore.WHITE + "Available coins: " + ", ".join(sorted(symbol_map.keys())))

    choice = input("Enter symbol for alert: ").strip().upper()
    coin = symbol_map.get(choice)
    if coin is None:
        print(Fore.YELLOW + "Symbol not found.")
        return

    coin_id = coin["id"]
    sym = coin.get("symbol", "").upper()

    print("Alert types:")
    print("1. Price alert (breaks above/below level)")
    print("2. RSI alert (crosses threshold)")
    alert_choice = input("Choose alert type (1-2): ").strip()

    if alert_choice == "1":
        alert_type = "price"
        current_price = coin.get("current_price", 0)
        print(f"Current price: {_fmt_price(current_price)}")
        threshold = float(input("Enter price threshold: ").strip())
        direction = input("Alert when price goes (above/below): ").strip().lower()
        if direction not in ["above", "below"]:
            print(Fore.RED + "Invalid direction.")
            return
    elif alert_choice == "2":
        alert_type = "rsi"
        threshold = float(input("Enter RSI threshold (0-100): ").strip())
        direction = input("Alert when RSI goes (above/below): ").strip().lower()
        if direction not in ["above", "below"]:
            print(Fore.RED + "Invalid direction.")
            return
    else:
        print(Fore.RED + "Invalid choice.")
        return

    save_alert(coin_id, alert_type, threshold, direction)
    print(Fore.GREEN + f"Alert set for {sym}: {alert_type.upper()} {direction} {threshold}")


def show_alerts() -> None:
    """Display all active alerts."""
    _divider("ACTIVE ALERTS")
    alerts = load_alerts()

    if not alerts:
        print(Fore.YELLOW + "No active alerts.")
        return

    rows = []
    for alert in alerts:
        rows.append([
            alert['coin_id'].upper(),
            alert['alert_type'].upper(),
            alert['threshold'],
            alert['direction'],
            alert['created_at'][:10],  # Date only
            alert['last_triggered'] or "Never"
        ])

    headers = ["Coin", "Type", "Threshold", "Direction", "Created", "Last Triggered"]
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print()


def run_backtest(coins: list[dict]) -> None:
    """Run backtest on a coin's historical data."""
    _divider("BACKTESTING")
    symbol_map = {coin.get("symbol", "").upper(): coin for coin in coins if coin.get("id")}
    print(Fore.WHITE + "Available coins: " + ", ".join(sorted(symbol_map.keys())))

    choice = input("Enter symbol for backtest: ").strip().upper()
    coin = symbol_map.get(choice)
    if coin is None:
        print(Fore.YELLOW + "Symbol not found.")
        return

    coin_id = coin["id"]
    sym = coin.get("symbol", "").upper()

    print("Available strategies:")
    print("1. RSI + MA crossover")
    strategy_choice = input("Choose strategy (1): ").strip()

    if strategy_choice == "1":
        strategy = "rsi_ma"
    else:
        print(Fore.RED + "Invalid choice.")
        return

    days = int(input("Enter backtest period in days (30-365): ").strip())
    if days < 30 or days > 365:
        print(Fore.RED + "Period must be between 30-365 days.")
        return

    print(Fore.WHITE + f"Running backtest for {sym} using {strategy} strategy over {days} days...\n")

    result = backtest_strategy(coin_id, strategy, days)

    if "error" in result:
        print(Fore.RED + result["error"])
        return

    print(Fore.CYAN + f"Backtest Results for {sym.upper()} - {strategy.upper()}:")
    print(f"Period: {result['period_days']} days")
    print(f"Total Trades: {result['total_trades']}")
    print(f"Win Rate: {result['win_rate']:.1f}%")
    print(f"Average Return per Trade: {result['avg_return']:.2f}%")
    print(f"Max Drawdown: {result['max_drawdown']:.2f}%")
    print()

    # Show recent trades
    trades = result['trades'][-5:]  # Last 5 trades
    if trades:
        print("Recent Trades:")
        for trade in trades:
            if trade['type'] == 'SELL':
                pnl_color = Fore.GREEN if trade.get('pnl', 0) > 0 else Fore.RED
                print(f"  {trade['date'].strftime('%Y-%m-%d')}: {trade['type']} @ {_fmt_price(trade['price'])} "
                      f"(PnL: {pnl_color}{trade.get('pnl', 0):+.2f}%)")
        print()


def show_charts(coins: list[dict]) -> None:
    """Display charts for a coin."""
    _divider("CHARTS & VISUALIZATION")
    symbol_map = {coin.get("symbol", "").upper(): coin for coin in coins if coin.get("id")}
    print(Fore.WHITE + "Available coins: " + ", ".join(sorted(symbol_map.keys())))

    choice = input("Enter symbol for charts: ").strip().upper()
    coin = symbol_map.get(choice)
    if coin is None:
        print(Fore.YELLOW + "Symbol not found.")
        return

    coin_id = coin["id"]
    sym = coin.get("symbol", "").upper()

    print("Chart types:")
    print("1. Price chart with indicators (matplotlib)")
    print("2. Candlestick chart (mplfinance)")
    print("3. Interactive chart (plotly)")
    print("4. Save price chart as PNG")

    chart_choice = input("Choose chart type (1-4): ").strip()

    days = int(input("Enter chart period in days (7-365): ").strip())
    if days < 7 or days > 365:
        days = 30  # Default

    if chart_choice == "1":
        plot_price_chart(coin_id, days)
    elif chart_choice == "2":
        plot_candlestick_chart(coin_id, days)
    elif chart_choice == "3":
        plot_interactive_chart(coin_id, days)
    elif chart_choice == "4":
        filename = f"{coin_id}_chart_{days}d.png"
        plot_price_chart(coin_id, days, filename)
    else:
        print(Fore.RED + "Invalid choice.")


MENU = """
{cyan}
     Crypto Price Analyzer   Top 10    
{reset}

  1  Live Prices
  2  Historical Analysis (7d + 30d)
  3  Trading Signals (RSI + MA)
  4  Technical Analysis
  5  Portfolio Summary
  6  Edit My Portfolio
  7  Setup Alert
  8  View Active Alerts
  9  Run Backtest
 10  Charts & Visualization
 11  Refresh market data
  0  Quit
"""


def main() -> None:
    print(Fore.CYAN + "\nLoading market data...")
    init_database()  # Initialize database on startup
    coins = fetch_top10()
    print(Fore.GREEN + f" Loaded {len(coins)} coins.\n")

    while True:
        print(MENU.format(cyan=Fore.CYAN, reset=Style.RESET_ALL))
        choice = input("Choose an option: ").strip()

        if choice == "1":
            show_live_prices(coins)
        elif choice == "2":
            show_historical(coins)
        elif choice == "3":
            show_signals(coins)
        elif choice == "4":
            show_technical_analysis(coins)
        elif choice == "5":
            show_portfolio(coins)
        elif choice == "6":
            edit_portfolio(coins)
        elif choice == "7":
            setup_alert(coins)
        elif choice == "8":
            show_alerts()
        elif choice == "9":
            run_backtest(coins)
        elif choice == "10":
            show_charts(coins)
        elif choice == "11":
            print(Fore.CYAN + "Refreshing market data...")
            coins = fetch_top10()
            print(Fore.GREEN + f" Refreshed. {datetime.now().strftime('%H:%M:%S')}\n")
        elif choice == "0":
            print(Fore.CYAN + "\nBye! \n")
            break
        else:
            print(Fore.YELLOW + "Invalid option  try again.\n")


if __name__ == "__main__":
    main()
