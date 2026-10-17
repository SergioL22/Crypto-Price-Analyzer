"""Public contracts for listing discovery and completed-session research."""
from typing import Literal
from pydantic import FiniteFloat
from backend_models import Contract, HistoryPoint


class AssetIdentity(Contract):
    id: str
    asset_class: Literal['crypto', 'stock', 'etf']
    provider: Literal['coingecko', 'twelvedata', 'demo']
    symbol: str
    name: str
    exchange: str
    currency: str
    timezone: str


class AssetCatalog(Contract):
    assets: list[AssetIdentity]
    stale: bool
    fetched_at_utc: str
    coverage: str


class SessionCoverage(Contract):
    start: str
    end: str
    expected_sessions: int
    observations: int
    missing_sessions: list[str]
    complete: bool
    latest_closed_session: str | None


class SessionPoint(HistoryPoint):
    break_before: bool


class DailyBar(Contract):
    date: str
    open: FiniteFloat
    high: FiniteFloat
    low: FiniteFloat
    close: FiniteFloat
    volume: FiniteFloat


class HistorySource(Contract):
    cache_hit: bool
    fetched_at_utc: str
    age_seconds: int


class StockResearch(Contract):
    asset: AssetIdentity
    generated_at_utc: str
    adjustment: Literal['splits', 'synthetic']
    window: SessionCoverage
    history: list[SessionPoint]
    bars: list[DailyBar]
    indicators: dict[str, FiniteFloat | None] | None
    limitations: list[str]
    history_source: HistorySource | None = None
