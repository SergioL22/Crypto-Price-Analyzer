# Phase 3: reproducible research data

This phase adds a command-line data pipeline. The dashboard is unchanged; visual polish remains after Phase 4. No model is trained and no accuracy figure is produced.

## Workflow

Run from the project folder with the project virtual environment. Stock/ETF capture uses the TWELVE_DATA_API_KEY environment variable in that terminal. Offline commands do not require a key.

```powershell
# Capture 180 calendar days, excluding the unfinished current UTC date.
.\.venv\Scripts\python.exe dataset_cli.py capture crypto bitcoin --days 180

# Capture a stock or ETF using its exact provider-qualified catalog ID.
.\.venv\Scripts\python.exe dataset_cli.py capture stock twelvedata:stock:XNGS:USD:AAPL --days 180
.\.venv\Scripts\python.exe dataset_cli.py capture etf twelvedata:etf:ARCX:USD:SPY --days 180

# List saved IDs, then replace SNAPSHOT_ID with a returned snapshot ID.
.\.venv\Scripts\python.exe dataset_cli.py list
.\.venv\Scripts\python.exe dataset_cli.py show SNAPSHOT_ID
.\.venv\Scripts\python.exe dataset_cli.py features SNAPSHOT_ID --horizon 5

# Optional: use a saved SPY snapshot as context for a stock snapshot.
.\.venv\Scripts\python.exe dataset_cli.py features STOCK_SNAPSHOT_ID --horizon 5 --benchmark SPY_SNAPSHOT_ID
```

`--horizon` accepts 1–30 observations on the asset's calendar. Five crypto observations mean five UTC dates; five stock observations mean five trading sessions. Capture accepts 35–364 calendar days. No multi-year entitlement is assumed.

The default store is `research_datasets.db` alongside the source files, separate from the runtime crypto database. It and its SQLite sidecars are ignored by Git. To use another path, place `--store PATH` before the command. Custom stores should stay outside the repository or be explicitly ignored.

## What is retained

Each snapshot contains asset identity, provider, capture time, expected sessions, normalized observed prices/volume, stock OHLC fields, adjustment basis, price definition, collection settings, missing-session dates and limitations. This is a normalized snapshot, not the original HTTP response. No keys, holdings, portfolio costs or LLM responses are included.

The full JSON payload has a SHA-256 identity. Identical payloads deduplicate. Revised prices or a new capture time produce another snapshot, preserving the old one. SQLite writes are transactional and the application exposes no edit/delete operation. Loading an artifact verifies its hash, so external modification is detected. Back up the separate SQLite file when the application is not writing to it; portfolio JSON backups do not include it.

Crypto uses provider daily samples and does not mislabel them exchange closing prices. Today's UTC date is excluded. Stocks/ETFs use completed regular sessions, accounting for holidays and shortened sessions, with the calendar package version recorded. A completed session whose bar is not yet available remains a visible gap.

## Feature version daily-v1

- One- and five-observation returns.
- Price relative to its 7- and 25-observation moving averages.
- Standard deviation of the last 20 one-observation returns (sample standard deviation, not annualized).
- Wilder RSI(14).
- MACD and its histogram divided by current price.
- Optional benchmark five-observation return and the asset's return minus that benchmark return.

Each feature uses the current completed observation and earlier observations only. Any decision using it must happen afterward. No centered window, backward filling, future-confirmed swing pattern, fitted scaler or future return enters the feature dictionary. Volume is preserved but intentionally omitted from this feature version because provider volume definitions differ.

Missing sessions divide history into independent segments. Indicators restart and need 35 consecutive observations before `feature_ready` becomes true. Labels cannot cross a gap. Benchmark context requires matching currency, timezone and adjustment basis, matches exact session dates, and never forward fills. Unavailable benchmark features make that row ineligible.

## Labels and reproducibility

Labels live in a separate `label` field: `end_session`, `forward_return`, and `up`. The return is price at t+h divided by price at t minus one; `up` is 1 only for a strictly positive return. The final h observations of a segment have no label. `supervised_ready` requires both ready features and an available label.

Derived artifacts reference their source and optional benchmark snapshot IDs, feature version, implementation hash, pandas version, horizon, feature-column allowlist and quality counts. Rebuilding with the same inputs and implementation gives the same artifact ID. Phase 4 must select inputs through `feature_columns`, never all numeric fields indiscriminately.

This is a prediction research target, not an executable strategy return. Transaction costs, next-session execution, chronological train/validation/test splits, label-boundary purging, train-only transformations and minimum evaluation sample requirements belong to Phase 4. A nonzero count of usable rows is not proof of enough data for reliable evaluation.

## Known limits and Phase 4 entry conditions

Provider history collected today may already reflect later corrections and split adjustments. These snapshots create a version history from collection onward; they do not reconstruct what was known on every past date. `historical_vintage_available` is explicitly false. No guarantees are made about delisted coverage, historical universe membership, ticker reuse, dividends, corporate-action publication timing, news or fundamentals.

Before making performance claims, define a small asset universe, acquire sufficient history under appropriate provider entitlements, inspect coverage and usable-row counts, choose targets/horizons, and reserve an untouched later evaluation period. Keep the data-availability and survivorship limitations attached to model reports. The pipeline is ready for baseline experiments; a production-quality training corpus is not supplied by the implementation.

Tests cover content identity/revisions, corruption detection, invalid numeric inputs, stock calendars, incomplete-day exclusion, gap handling, exact label horizons, future-perturbation and prefix invariance, optional benchmark causality, and offline command reproducibility. Development tests use synthetic data; no live dataset capture is claimed.
