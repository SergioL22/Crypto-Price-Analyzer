"""HTTP request and response contracts; no terminal or storage dependencies."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

CoinId = Annotated[str, Field(strict=True, min_length=1, max_length=100, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')]
BacktestDays = Annotated[int, Field(strict=True, ge=30, le=365)]
EvidenceDays = Annotated[int, Field(strict=True, ge=35, le=365)]
Amount = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Position(Contract):
    amount: Amount
    avg_buy_price: Amount = 0.0


class BacktestRequest(Contract):
    coin_id: CoinId
    days: BacktestDays = 90
    strategy: Literal['rsi_ma'] = 'rsi_ma'


class RecommendationRequest(Contract):
    coin_id: CoinId
    days: EvidenceDays = 90
    selected_position: Position | None = None


class Coverage(Contract):
    requested_days: int
    expected_start: str
    expected_end: str
    observations: int
    start: str | None
    end: str | None
    missing_days: int
    internal_missing_days: int
    leading_missing_days: int
    trailing_missing_days: int
    complete: bool
    latest_observation_age_days: int | None
    definition: str


class Indicators(Contract):
    latest_history_price_usd: FiniteFloat
    live_price_usd: FiniteFloat | None
    rsi_14: FiniteFloat
    ma_7: FiniteFloat
    ma_25: FiniteFloat
    macd: FiniteFloat
    macd_signal: FiniteFloat
    macd_histogram: FiniteFloat
    bollinger_lower: FiniteFloat
    bollinger_middle: FiniteFloat
    bollinger_upper: FiniteFloat
    support: list[FiniteFloat]
    resistance: list[FiniteFloat]
    patterns: list[str]
    average_volume_20: FiniteFloat | None
    volume_spikes: list[str]


class BacktestSummary(Contract):
    strategy: Literal['rsi_ma']
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: FiniteFloat | None
    average_closed_trade_return_pct: FiniteFloat | None
    asset_max_drawdown_pct: FiniteFloat
    open_position: bool


class ExcludedPortfolio(Contract):
    included: Literal[False]


class IncludedPortfolio(Contract):
    included: Literal[True]
    amount: FiniteFloat
    average_buy_price_usd: FiniteFloat | None
    valuation_price_usd: FiniteFloat
    value_usd: FiniteFloat
    unrealized_pnl_usd: FiniteFloat | None
    scope: str


class Evidence(Contract):
    coin_id: str
    currency: Literal['usd']
    generated_at_utc: str
    window: Coverage
    indicators: Indicators
    backtest: BacktestSummary
    portfolio: ExcludedPortfolio | IncludedPortfolio
    limitations: list[str]


class Citation(Contract):
    explanation: Annotated[str, Field(min_length=1, max_length=1200)]
    evidence_keys: Annotated[list[str], Field(min_length=1, max_length=12)]


class Recommendation(Contract):
    action: Literal['BUY', 'HOLD', 'SELL']
    confidence: Literal['low', 'medium', 'high']
    confidence_explanation: str
    summary: str
    reasons: Annotated[list[Citation], Field(min_length=1, max_length=6)]
    risks: Annotated[list[Citation], Field(min_length=1, max_length=6)]


class SafeError(Contract):
    code: str
    message: str


class ErrorResponse(Contract):
    error: SafeError
    coverage: Coverage | None = None


class RecommendationResponse(Contract):
    evidence: Evidence
    model: str | None
    recommendation_status: Literal['completed', 'unavailable']
    recommendation: Recommendation | None
    ai_error: SafeError | None


class Trade(Contract):
    type: Literal['BUY', 'SELL']
    price: FiniteFloat
    date: str
    pnl: FiniteFloat | None = None


class BacktestResponse(Contract):
    coin_id: str
    currency: Literal['usd']
    window: Coverage
    summary: BacktestSummary
    trades: list[Trade]
    limitations: list[str]


NonnegativeMarketValue = Annotated[FiniteFloat, Field(ge=0)]


class Market(Contract):
    id: str
    symbol: str | None = None
    name: str | None = None
    current_price: NonnegativeMarketValue | None = None
    market_cap: NonnegativeMarketValue | None = None
    total_volume: NonnegativeMarketValue | None = None
    price_change_percentage_1h_in_currency: FiniteFloat | None = None
    price_change_percentage_24h_in_currency: FiniteFloat | None = None
    price_change_percentage_7d_in_currency: FiniteFloat | None = None


class PricesResponse(Contract):
    currency: Literal['usd']
    fetched_at_utc: str
    markets: list[Market]


class HealthResponse(Contract):
    status: Literal['ok']
