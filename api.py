"""CoinGecko requests and normalization of market data."""
from numbers import Integral
import time
import logging
import pandas as pd
import requests
import data as storage

BASE_URL = "https://api.coingecko.com/api/v3/"
CURRENCY = "usd"
TOP_N = 10
OHLC_DAYS = (1, 7, 14, 30, 90, 180, 365)
logger = logging.getLogger(__name__)


class UpstreamError(RuntimeError):
    """CoinGecko request or payload failed; HTTP adapters need not parse messages."""


def _get(endpoint: str, params: dict | None = None) -> dict:
    """Send a GET request to CoinGecko with retry logic.

    Raises RuntimeError on failure instead of exiting the process, so a single
    bad request can't kill the whole interactive session -- callers decide how
    to handle it (show an error and keep going, mostly).
    """
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
                logger.warning("Rate limited - waiting %ss...", wait)
                time.sleep(wait)
                continue
            raise UpstreamError(f"CoinGecko HTTP error: {error}") from error
        except requests.exceptions.RequestException as error:
            raise UpstreamError(f"CoinGecko network error: {error}") from error

    raise UpstreamError("CoinGecko max retries reached (rate limited).")


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


def fetch_history(coin_id: str, days: int, *, persist: bool = True) -> pd.DataFrame:
    data = _get(f"coins/{coin_id}/market_chart", {
        "vs_currency": CURRENCY,
        "days": days,
        "interval": "daily",
    })
    try:
        if not isinstance(data, dict) or not isinstance(data.get("prices"), list):
            raise ValueError("Missing or invalid prices array")
        prices = data["prices"]
        volumes = data.get("total_volumes", [])
        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        if len(volumes) == len(df):
            df["volume"] = [volume[1] for volume in volumes]
        else:
            df["volume"] = None
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.date
        df = df.groupby(["date"])[["price", "volume"]].last().reset_index()

    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as error:
        raise UpstreamError("CoinGecko returned malformed history.") from error

    # Save to database for persistence
    if persist:
        storage.save_price_data(coin_id, df)

    return df


def fetch_ohlc(coin_id: str, days: int) -> pd.DataFrame:
    """Fetch real OHLC data from CoinGecko. Returns DataFrame with Open/High/Low/Close index by datetime."""
    if (not isinstance(days, Integral) or isinstance(days, bool)) or days not in OHLC_DAYS:
        raise RuntimeError(f'Unsupported OHLC window {days}; choose one of {OHLC_DAYS}.')
    days = int(days)
    data = _get(f"coins/{coin_id}/ohlc", {"vs_currency": CURRENCY, "days": days})
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close"])
    df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    return df[["Open", "High", "Low", "Close"]]

