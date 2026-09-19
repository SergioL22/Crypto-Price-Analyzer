"""Terminal commands, interactive menus, alerts, and chart presentation."""
import json
import sys
import time
from datetime import datetime
from typing import Optional
import typer
import pandas as pd
from colorama import Fore, Style, init
from tabulate import tabulate
import api
import data
import analysis
import recommendations
from llm import OpenAIRecommender


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
 12  AI Recommendation
  0  Quit
"""

app = typer.Typer(
    name="crypto",
    help="Crypto Price Analyzer — top 10 cryptos via CoinGecko.",
    add_completion=False,
)


def log_alert(coin_id: str, alert_type: str, message: str) -> None:
    """Log alert to file and console."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {coin_id.upper()}: {alert_type} - {message}"

    # Print to console with color
    print(Fore.YELLOW + f"🚨 ALERT: {log_message}")

    data.append_alert_log(log_message)


def check_alerts(coins: list[dict]) -> None:
    """Check all active alerts against current data."""
    alerts = data.load_alerts(active_only=True)
    if not alerts:
        return

    price_map = {coin['id']: coin['current_price'] for coin in coins}

    for alert in alerts:
        coin_id = alert['coin_id']
        alert_type = alert['alert_type']
        threshold = alert['threshold']
        direction = alert['direction']

        if alert_type == 'price':
            if coin_id not in price_map:
                continue
            current_price = price_map[coin_id]

            if direction == 'above' and current_price > threshold:
                log_alert(coin_id, 'PRICE ALERT', f"Price ${current_price:.2f} broke above ${threshold:.2f}")
                data.mark_alert_triggered(alert['id'])

            elif direction == 'below' and current_price < threshold:
                log_alert(coin_id, 'PRICE ALERT', f"Price ${current_price:.2f} broke below ${threshold:.2f}")
                data.mark_alert_triggered(alert['id'])

        elif alert_type == 'rsi':
            # Need to calculate RSI for this coin. This hits the API, so errors
            # are shown (not silently swallowed) and coins are spaced out to
            # avoid tripping CoinGecko's rate limit when several alerts exist.
            try:
                df = api.fetch_history(coin_id, 30)
                if len(df) >= 15:
                    rsi = analysis.compute_rsi(df['price'])
                    if direction == 'above' and rsi > threshold:
                        log_alert(coin_id, 'RSI ALERT', f"RSI {rsi:.1f} crossed above {threshold}")
                    elif direction == 'below' and rsi < threshold:
                        log_alert(coin_id, 'RSI ALERT', f"RSI {rsi:.1f} crossed below {threshold}")
            except Exception as error:
                print(Fore.YELLOW + f"Could not check RSI alert for {coin_id}: {error}")
            time.sleep(0.6)


def plot_price_chart(coin_id: str, days: int = 30, save_path: Optional[str] = None) -> None:
    """Create and display/save a price chart with technical indicators."""
    import matplotlib.pyplot as plt
    df = data.load_price_data(coin_id, days)
    if df is None or len(df) < 20:
        print(Fore.RED + "Insufficient data for charting.")
        return

    prices = df['price']

    # Calculate indicators
    ma7 = prices.rolling(7).mean()
    ma25 = prices.rolling(25).mean()
    bb_mid, bb_upper, bb_lower = analysis.compute_bollinger_bands(prices)

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
    """Create and display/save a candlestick chart using real OHLC data from CoinGecko."""
    import mplfinance as mpf
    print(Fore.WHITE + f"Fetching OHLC data for {coin_id.upper()}...")
    ohlc_df = api.fetch_ohlc(coin_id, days)
    if ohlc_df.empty or len(ohlc_df) < 5:
        print(Fore.RED + "Insufficient OHLC data for candlestick chart.")
        return

    print(f"Requested OHLC window: {days} days; returned candles: "
          f"{ohlc_df.index.min()} to {ohlc_df.index.max()} ({len(ohlc_df)} candles).")

    # mplfinance requires a Volume column
    ohlc_df["Volume"] = 0

    kwargs = dict(type='candle', style='charles',
                  title=f'{coin_id.upper()} Candlestick Chart (requested {days} days)')
    if save_path:
        mpf.plot(ohlc_df, **kwargs, savefig=dict(fname=save_path, dpi=300, bbox_inches='tight'))
        print(Fore.GREEN + f"Candlestick chart saved to {save_path}")
    else:
        mpf.plot(ohlc_df, **kwargs)


def plot_interactive_chart(coin_id: str, days: int = 30) -> None:
    """Create an interactive Plotly chart."""
    import plotly.graph_objects as go
    df = data.load_price_data(coin_id, days)
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


def _ask_int(prompt: str, min_val: int | None = None, max_val: int | None = None) -> int | None:
    """Prompt for an integer, re-asking on invalid input. Returns None on empty."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            val = int(raw)
        except ValueError:
            print(Fore.YELLOW + "Please enter a whole number.")
            continue
        if min_val is not None and val < min_val:
            print(Fore.YELLOW + f"Must be at least {min_val}.")
            continue
        if max_val is not None and val > max_val:
            print(Fore.YELLOW + f"Must be at most {max_val}.")
            continue
        return val


def _ask_float(prompt: str) -> float | None:
    """Prompt for a float, re-asking on invalid input. Returns None on empty."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            print(Fore.YELLOW + "Please enter a valid number.")


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
            df = api.fetch_history(cid, 30)
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
            df = api.fetch_history(cid, 30)
        except Exception:
            continue

        if len(df) < 15:
            continue

        prices = df["price"]
        ma7 = prices.tail(7).mean()
        ma25 = prices.tail(25).mean() if len(prices) >= 25 else prices.mean()
        rsi = analysis.compute_rsi(prices)
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
        df = api.fetch_history(cid, 60)
    except Exception as error:
        print(Fore.RED + f"Failed to fetch history for {sym}: {error}")
        return

    if len(df) < 20:
        print(Fore.YELLOW + "Not enough history to perform technical analysis.")
        return

    prices = df["price"]
    volumes = df["volume"] if "volume" in df else pd.Series(dtype=float)

    bb_mid, bb_upper, bb_lower = analysis.compute_bollinger_bands(prices)
    macd, signal_line, hist = analysis.compute_macd(prices)
    support, resistance = analysis.find_support_resistance(prices)
    patterns = analysis.describe_patterns(prices)
    volume_spikes, avg_volume = analysis.analyze_volume(df)

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
        ["Historical swing lows (support candidates)", ", ".join(_fmt_price(level) for level in support)],
        ["Historical swing highs (resistance candidates)", ", ".join(_fmt_price(level) for level in resistance)],
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


def edit_portfolio(coins: list[dict]) -> None:
    portfolio = data.load_portfolio()
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

    data.save_portfolio(portfolio)
    print(Fore.GREEN + f"Portfolio saved to {data.PORTFOLIO_FILE}")


def show_portfolio(coins: list[dict]) -> None:
    _divider("PORTFOLIO TRACKER")
    portfolio = data.load_portfolio()

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
        threshold = _ask_float("Enter price threshold: ")
        if threshold is None:
            return
        direction = input("Alert when price goes (above/below): ").strip().lower()
        if direction not in ["above", "below"]:
            print(Fore.RED + "Invalid direction.")
            return
    elif alert_choice == "2":
        alert_type = "rsi"
        threshold = _ask_float("Enter RSI threshold (0-100): ")
        if threshold is None:
            return
        direction = input("Alert when RSI goes (above/below): ").strip().lower()
        if direction not in ["above", "below"]:
            print(Fore.RED + "Invalid direction.")
            return
    else:
        print(Fore.RED + "Invalid choice.")
        return

    data.save_alert(coin_id, alert_type, threshold, direction)
    print(Fore.GREEN + f"Alert set for {sym}: {alert_type.upper()} {direction} {threshold}")


def show_alerts() -> None:
    """Display and manage all alerts."""
    while True:
        _divider("ALERT MANAGEMENT")
        alerts = data.load_alerts()

        if not alerts:
            print(Fore.YELLOW + "No alerts configured.")
            return

        rows = []
        for alert in alerts:
            status = Fore.GREEN + "Active" if alert['is_active'] else Fore.RED + "Paused"
            rows.append([
                alert['id'],
                alert['coin_id'].upper(),
                alert['alert_type'].upper(),
                alert['threshold'],
                alert['direction'],
                status,
                alert['last_triggered'] or "Never",
            ])

        headers = ["ID", "Coin", "Type", "Threshold", "Direction", "Status", "Last Triggered"]
        print(tabulate(rows, headers=headers, tablefmt="simple"))
        print()
        print(Fore.WHITE + "  D <id>  delete alert     T <id>  toggle active/paused     Enter  back")
        print()

        raw = input("Action: ").strip()
        if not raw:
            break

        parts = raw.split()
        if len(parts) != 2:
            print(Fore.YELLOW + "Use: D <id> or T <id>\n")
            continue

        action, id_str = parts[0].upper(), parts[1]
        try:
            alert_id = int(id_str)
        except ValueError:
            print(Fore.YELLOW + "Invalid ID.\n")
            continue

        if action == "D":
            data.delete_alert(alert_id)
            print(Fore.GREEN + f"Alert {alert_id} deleted.\n")
        elif action == "T":
            new_state = data.toggle_alert(alert_id)
            if new_state is None:
                print(Fore.YELLOW + f"Alert {alert_id} not found.\n")
            else:
                state_str = "activated" if new_state else "paused"
                print(Fore.GREEN + f"Alert {alert_id} {state_str}.\n")
        else:
            print(Fore.YELLOW + "Unknown action. Use D or T.\n")


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

    days = _ask_int("Enter backtest period in days (30-365): ", min_val=30, max_val=365)
    if days is None:
        return

    print(Fore.WHITE + f"Running backtest for {sym} using {strategy} strategy over {days} days...\n")

    result = analysis.backtest_strategy(coin_id, strategy, days)

    if "error" in result:
        print(Fore.RED + result["error"])
        return

    print(Fore.CYAN + f"Backtest Results for {sym.upper()} - {strategy.upper()}:")
    print(f"Requested window: {result['period_days']} days")
    print(f"Observed data: {result['start_date']} to {result['end_date']} "
          f"({result['observations']} observations)")
    if 'window' in result and not result['window']['complete']:
        print(f"Incomplete requested window: {result['window']['missing_days']} daily observations missing.")
    print(f"Closed trades: {result['total_trades']}")
    if result['total_trades']:
        print(f"Win rate (closed trades): {result['win_rate']:.1f}%")
        print(f"Average closed-trade return: {result['avg_return']:.2f}%")
    else:
        print("Win rate (closed trades): N/A")
        print("Average closed-trade return: N/A")
    print(f"Underlying asset max drawdown: {result['max_drawdown']:.2f}% (not strategy equity)")
    print(f"Open position: {'YES' if result['open_position'] else 'NO'}")
    print("Limitations: fees/slippage excluded; same-bar fills; open-position P&L excluded.")
    print("Closed-trade returns are not total portfolio returns.\n")

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

    if chart_choice == "2":
        print(f"Supported OHLC windows: {', '.join(map(str, api.OHLC_DAYS))}")
    days = _ask_int("Enter chart period in days: ", min_val=1 if chart_choice == "2" else 7, max_val=365)
    if days is None:
        days = 30

    if chart_choice == "1":
        plot_price_chart(coin_id, days)
    elif chart_choice == "2":
        if days not in api.OHLC_DAYS:
            print(Fore.YELLOW + f"Unsupported OHLC window. Choose one of {api.OHLC_DAYS}.")
            return
        plot_candlestick_chart(coin_id, days)
    elif chart_choice == "3":
        plot_interactive_chart(coin_id, days)
    elif chart_choice == "4":
        filename = f"{coin_id}_chart_{days}d.png"
        plot_price_chart(coin_id, days, filename)
    else:
        print(Fore.RED + "Invalid choice.")


def _load() -> list[dict]:
    """Initialize DB and fetch live market data.

    Returns an empty list (rather than crashing the whole process) if
    CoinGecko can't be reached.
    """
    data.init_database()
    print(Fore.CYAN + "\nLoading market data...")
    try:
        coins = api.fetch_top10()
    except RuntimeError as error:
        print(Fore.RED + f"Could not load market data: {error}")
        print(Fore.YELLOW + "Check your internet connection and try again.\n")
        return []
    print(Fore.GREEN + f"Loaded {len(coins)} coins.\n")
    return coins


@app.command()
def prices() -> None:
    """Live prices for the top 10 cryptos by market cap."""
    show_live_prices(_load())


@app.command()
def history() -> None:
    """7-day and 30-day historical price analysis."""
    show_historical(_load())


@app.command()
def signals() -> None:
    """Trading signals using RSI and moving averages."""
    show_signals(_load())


@app.command()
def technical() -> None:
    """Detailed technical analysis for a chosen coin."""
    show_technical_analysis(_load())


@app.command()
def portfolio() -> None:
    """Portfolio summary with current value and P&L."""
    show_portfolio(_load())


@app.command(name="edit-portfolio")
def edit_portfolio_cmd() -> None:
    """Edit portfolio holdings and average buy prices."""
    edit_portfolio(_load())


@app.command(name="setup-alert")
def setup_alert_cmd() -> None:
    """Set up a price or RSI alert for a coin."""
    setup_alert(_load())


@app.command(name="alerts")
def alerts_cmd() -> None:
    """View all active alerts."""
    data.init_database()
    show_alerts()


@app.command()
def backtest() -> None:
    """Backtest a trading strategy on historical data."""
    run_backtest(_load())


@app.command()
def charts() -> None:
    """Display charts for a chosen coin."""
    show_charts(_load())


def show_recommendation(coin_id: str, days: int = 90, include_portfolio: bool = True,
                        evidence_only: bool = False) -> bool:
    """Always show computed evidence before requesting an optional AI assessment."""
    try:
        data.init_database()
        frame = api.fetch_history(coin_id, days)
        portfolio = data.load_portfolio() if include_portfolio else None
        evidence = recommendations.build_evidence(coin_id, frame, days=days, portfolio=portfolio)
    except (RuntimeError, ValueError, OSError) as error:
        print(Fore.RED + f"Could not prepare recommendation evidence: {error}")
        return False
    _divider(f"RECOMMENDATION EVIDENCE: {coin_id.upper()}")
    fields = recommendations.evidence_fields(evidence)
    rows = [[key, json.dumps(value, ensure_ascii=True, allow_nan=False)] for key, value in fields.items()]
    print(tabulate(rows, headers=['Evidence field', 'Computed value'], tablefmt='grid',
                   maxcolwidths=[45, 85], disable_numparse=True))
    if evidence_only:
        print("Evidence only: no request sent to OpenAI.")
        return True
    try:
        provider = OpenAIRecommender.from_environment()
        print(f"\nRequesting OpenAI assessment ({provider.model}); sending the evidence above.")
        result = provider.recommend(evidence)
    except recommendations.RecommendationError as error:
        print(Fore.YELLOW + f"AI recommendation unavailable: {error}")
        return False
    print(Fore.CYAN + f"\nAI assessment: {result['action']} | Confidence: {result['confidence'].upper()}")
    print("Confidence is the model's assessment of evidence, not a probability of profit.")
    print(result['confidence_explanation'])
    print(result['summary'])
    for category in ('reasons', 'risks'):
        print(category.capitalize() + ':')
        for item in result[category]:
            citations = '; '.join(f"{key} = {json.dumps(fields[key], ensure_ascii=True)}"
                                  for key in item['evidence_keys'])
            print(f"- {item['explanation']} [{citations}]")
    print("Informational assessment only; no trades are executed.\n")
    return True


@app.command()
def recommend(
    coin_id: str = typer.Argument(..., help="CoinGecko ID, e.g. bitcoin (not BTC)."),
    days: int = typer.Option(90, min=35, max=365, help="Requested history window."),
    include_portfolio: bool = typer.Option(True, '--portfolio/--no-portfolio', help="Include the selected coin's holding."),
    evidence_only: bool = typer.Option(False, '--evidence-only', help="Show evidence without calling OpenAI."),
) -> None:
    """Show indicator evidence and an optional OpenAI BUY/HOLD/SELL assessment."""
    if not show_recommendation(coin_id, days, include_portfolio, evidence_only):
        raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the interactive menu (default when no subcommand is given)."""
    if ctx.invoked_subcommand is not None:
        return

    coins = _load()
    if not coins:
        print(Fore.RED + "Exiting: no market data available.\n")
        return

    while True:
        print(MENU.format(cyan=Fore.CYAN, reset=Style.RESET_ALL))
        choice = input("Choose an option: ").strip()

        try:
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
                coins = api.fetch_top10()
                print(Fore.GREEN + f"Refreshed. {datetime.now().strftime('%H:%M:%S')}\n")
            elif choice == "12":
                coin_id = input("CoinGecko ID (e.g. bitcoin): ").strip().lower()
                if coin_id:
                    show_recommendation(coin_id)
            elif choice == "0":
                print(Fore.CYAN + "\nBye!\n")
                break
            else:
                print(Fore.YELLOW + "Invalid option - try again.\n")
        except RuntimeError as error:
            print(Fore.RED + f"\n{error}")
            print(Fore.YELLOW + "That request failed, but the app is still running - try again.\n")


def run() -> None:
    """Configure the terminal only when launching the CLI."""
    init(autoreset=True)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    app()
