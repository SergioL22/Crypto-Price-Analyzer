# Crypto Price Analyzer

A command-line cryptocurrency price analysis tool using CoinGecko data.

> **Work in progress.** This project is actively being improved, and planned features are listed below.

## What this program does

This tool provides a simple terminal-based dashboard for cryptocurrency market data and technical indicators.

Current capabilities include:

- Fetching live prices for the top 10 cryptocurrencies by market cap
- Displaying recent price changes over 1 hour, 24 hours, and 7 days
- Fetching historical price data for analysis and persistence
- Showing historical summaries for 7-day and 30-day performance
- Generating trading signals using RSI and moving averages
- Performing technical analysis with Bollinger Bands, MACD, support/resistance, volume spikes, and chart patterns
- Maintaining a local portfolio tracker with holdings, average buy price, current value, and P&L
- Managing basic alerts for price and RSI thresholds
- Creating price and candlestick charts using matplotlib, mplfinance, and Plotly

## How it works

1. The app uses the CoinGecko public API to fetch market data and historical price charts.
2. Historical price data is saved locally in `crypto_data.db` for later analysis.
3. Portfolio holdings are stored in `portfolio.json` so your positions persist between runs.
4. The user interacts with a simple menu-driven interface in the terminal.
5. Technical indicators and trading signals are computed from the historical price series using pandas.
6. Alerts are stored in SQLite and can be triggered when price or RSI conditions are met.

## Requirements

- Python 3.11+
- `requests`
- `pandas`
- `tabulate`
- `colorama`
- `matplotlib`
- `plotly`
- `mplfinance`

## Setup

1. Create and activate a virtual environment (optional but recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Usage

Run the main script:

```powershell
python main.py
```

Then choose from the menu options to view live prices, historical analysis, trading signals, technical analysis, portfolio details, alerts, backtests, or charts.

## Planned improvements

- Add a proper CLI command interface using `typer` or `argparse`
- Add portfolio transaction history, realized/unrealized P&L, and multi-currency support
- Add a separate watchlist feature for tracking coins without holdings
- Improve alert management with enable/disable/delete actions and notification delivery (email/Telegram/desktop)
- Add more indicator-based alerts such as MA crossovers, MACD signals, and support/resistance breaks
- Use actual OHLC historical data for candlestick charts instead of approximate values
- Add more technical indicators like EMA, ATR, and Ichimoku Clouds
- Add unit tests for indicator calculations and data handling
- Refactor code into modules (`api.py`, `data.py`, `analysis.py`, `ui.py`)
- Add GitHub Actions or CI for automated testing
- Improve error handling and user input validation

## Notes

- CoinGecko public API is used and does not require an API key.
- This tool is for informational purposes only and not financial advice.
