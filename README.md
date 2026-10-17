# Crypto Price Analyzer

A command-line cryptocurrency price analysis tool that fetches CoinGecko data, computes technical indicators, and supports portfolio tracking and alerts. It is designed to run from the terminal with live market data, historical analysis, and portfolio monitoring features.

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

- Add portfolio transaction history, realized/unrealized P&L, and multi-currency support
- Add a separate watchlist feature for tracking coins without holdings
- Improve alert management with enable/disable/delete actions and notification delivery (email/Telegram/desktop)
- Add more indicator-based alerts such as MA crossovers, MACD signals, and support/resistance breaks
- Use actual OHLC historical data for candlestick charts instead of approximate values
- Add more technical indicators like EMA, ATR, and Ichimoku Clouds
- Add authentication and deployment design before exposing the local backend to mobile or other users
- Improve error handling and user input validation

## Notes

- CoinGecko public API is used and does not require an API key.
- This tool is for informational purposes only and not financial advice.

## Code organization

- `main.py`: small CLI entry point; existing commands and interactive menu remain available.
- `api.py`: CoinGecko requests, retries, and data normalization. `fetch_history` continues to save fetched data through `data.py`.
- `data.py`: SQLite storage, portfolio files, and alert log persistence. Storage paths remain relative to the working directory.
- `analysis.py`: RSI, MACD, Bollinger Bands, swing/pattern detection, volume analysis, and backtesting.
- `ui.py`: Typer commands, terminal formatting, interactive alert checks, and charts. Chart dependencies load only when needed.
- `history_window.py`: shared UTC calendar-date selection and coverage metadata for fresh backtests and recommendation evidence.
- `recommendations.py`: JSON-safe evidence construction and recommendation validation.
- `llm.py`: replaceable OpenAI adapter using the existing `requests` dependency.

Import reusable functions from their owning modules instead of `main`:

```python
from analysis import compute_rsi, backtest_dataframe

rsi = compute_rsi(history["price"])
result = backtest_dataframe(history, "bitcoin", strategy="rsi_ma", days=90)
```

The DataFrame backtest accepts a date-indexed `price` column and performs no fetching or persistence. Supply the requested historical window yourself; `days` labels that window. `backtest_strategy` fetches fresh history, selects the requested UTC calendar dates directly from that response, and saves the results. It never rereads cached rows for the calculation. The existing max-drawdown metric describes the underlying prices, not a simulated strategy equity curve.

Importing these modules does not initialize storage or reconfigure terminal streams. Call `data.init_database()` before using database-backed operations. Portfolio save messages and alert presentation belong to the UI.

Run offline tests with:

```powershell
python -m pytest -q
```

## AI recommendations

The `recommend` command (also menu option 12) shows the computed evidence first, then an OpenAI BUY/HOLD/SELL assessment with a confidence level, explanation, evidence references, and risks. Confidence is the model's qualitative assessment, **not a calibrated probability of profit**. No trades are executed. Model explanations still need human review; valid references do not guarantee that an explanation interprets the evidence correctly.

Set these variables in the PowerShell session where you launch the app:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_MODEL = "your-supported-model-id"
python main.py recommend bitcoin --days 90
```

Choose a model available to your account that supports the Responses API and structured outputs. There is no hard-coded model default. Credentials are read only when requesting AI, never saved to the database or included in evidence. The adapter sends one bounded request with `store: false`; API usage may incur charges. Request/response handling follows the [official OpenAI structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

Inspect the evidence without an OpenAI key or model call:

```powershell
python main.py recommend bitcoin --days 90 --evidence-only
```

The command still fetches fresh CoinGecko history. It computes indicators and backtest results from that same returned window, rather than reading unrelated cached rows. The evidence records actual dates, observation count, missing days, and limitations. At least 35 daily prices within the requested 35–365 day window are required, and the latest observation must be no more than two days old. Missing observations and partial coverage are explicitly disclosed. The daily API sample may include an incomplete current day.

By default, the selected coin's holding amount, cost basis (if known), value, and unrealized P&L are included in the evidence sent to OpenAI. Other holdings are not sent, and total portfolio concentration is unknown. Valuation uses the latest historical sample. To exclude holdings entirely:

```powershell
python main.py recommend bitcoin --no-portfolio
```

Zero closed backtest trades produce unavailable win-rate/return values rather than a misleading zero. The evidence also discloses fees/slippage exclusions, same-bar fills, omitted open-position P&L, and the asset-versus-strategy drawdown distinction.

API failures, refusals, incomplete answers, and invalid evidence references leave the raw evidence visible and report that AI is unavailable. The CLI returns exit code 1 in that case; the interactive menu remains usable. It never fabricates a fallback BUY/HOLD/SELL decision.

For future backend integration, call `recommendations.build_evidence(...)`, then an adapter's `recommend(evidence)`. `OpenAIRecommender` implements that interface and validates model output. The evidence builder does not fetch data, write files, or configure terminal output. The local FastAPI adapter is described below.

## Numerical audit follow-up

RSI now starts with the arithmetic mean of the first 14 gains/losses and then applies Wilder's recurrence. `compute_rsi_series` produces the complete causal series; the latest indicator and every backtest observation use that same calculation. The backtest no longer restarts RSI on each 26-bar slice. This correction can change past trade signals and metrics; rerun analyses to get corrected results. Previously saved backtest summaries are not rewritten.

Zigzag support/resistance and pattern detection now exclude the trailing extreme until its own threshold reversal occurs. An earlier confirmed swing cannot confirm the latest endpoint. Pattern labels still mean possible formations, not confirmed neckline breakouts.

The plain backtest command distinguishes the requested window from observed dates and row count, labels drawdown as underlying-asset drawdown, shows whether a position remains open, and reports N/A for closed-trade metrics when none closed. Unsupported strategy names return an error. Fees/slippage, same-bar execution, and omitted open-position P&L remain disclosed strategy simplifications. OHLC requests now reject unsupported windows instead of silently snapping to a different period.

## Window and citation contracts

For recommendations and fresh backtests, N days means exactly N UTC calendar dates ending today (inclusive), beginning N-1 dates ago. A 90-day request on September 18, 2026 spans June 21–September 18. The current day can be incomplete. Extra older/future rows are excluded; missing dates are never filled from the cache.

Evidence reports expected and observed dates, observations, total missing dates, and separate leading, internal, and trailing gaps. A full 90-row daily response has no missing-window warning. Zero internal gaps does not imply full coverage if dates are missing at either boundary. The low-level cache reader retains its existing cutoff semantics; it is not the source for fresh backtests.

Candlestick requests accept exactly 1, 7, 14, 30, 90, 180, or 365 days; other periods fail with an explicit supported-period list before an API request. These options follow the [CoinGecko OHLC guide](https://www.coingecko.com/learn/how-to-fetch-historical-crypto-data-with-python). The chart displays the returned candle date range as well as the requested window.

Model `reasons` and `risks` now both contain objects with `explanation` and `evidence_keys` (an array of one to twelve unique field paths). The prompt requests every supporting field, and the terminal displays the cited values directly from computed evidence. All supplied paths are validated, including risk citations. This changes the former single-key/string-risk response contract; older responses should not be fed to the new validator.

Citation validation checks reference existence and structure. It does **not** prove that every number or inference in free-form prose is accurate or that the model cited every relevant field. Summaries, confidence, and interpretation still require human review. No hard-coded confidence override is applied.

The support/resistance evidence lists remain historical swing lows/highs. Their interpretation is now explicitly disclosed: they are not filtered by current price, and broken highs are not automatically treated as overhead resistance. Pattern detections remain possible formations rather than confirmed breakouts.

## Local FastAPI backend

This is a single-user local prototype. Start one worker bound to loopback; authentication and public/mobile deployment are not implemented. The API reuses the calculations without importing CLI presentation code.

```powershell
python -m pip install -r requirements-backend.txt
python -m uvicorn backend:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open `http://127.0.0.1:8000/docs` for the generated schema and request forms. Stop with Ctrl+C. OpenAI configuration comes from the server process's `OPENAI_API_KEY` and `OPENAI_MODEL`; analysis/backtests require neither. There are no startup provider calls or database initialization.

| Endpoint | Input | Result |
| --- | --- | --- |
| `GET /health` | None | Liveness only; no external work |
| `GET /v1/prices` | None | Top-10 market fields, preserving missing values as null; negative price/cap/volume rejected, signed percentage changes allowed |
| `GET /v1/analysis/{coin_id}?days=90` | CoinGecko slug; 35–365 days | Indicator, coverage, backtest, and limitation evidence; no AI |
| `POST /v1/backtests` | `coin_id`, `days` 30–365, `strategy` = `rsi_ma` | Fresh-window results and UTC trade timestamps |
| `POST /v1/recommendations` | `coin_id`, `days` 35–365, optional `selected_position` | Exact evidence plus validated AI assessment, or explicit unavailability |

For example, from another PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod 'http://127.0.0.1:8000/v1/analysis/bitcoin?days=90'
Invoke-RestMethod http://127.0.0.1:8000/v1/backtests -Method Post -ContentType 'application/json' -Body '{"coin_id":"bitcoin","days":90,"strategy":"rsi_ma"}'
```

A recommendation POST makes a billable OpenAI request if configured:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/recommendations -Method Post -ContentType 'application/json' -Body '{"coin_id":"bitcoin","days":90}'
```

Optional position input is `"selected_position":{"amount":0.5,"avg_buy_price":60000}`. It is used only for this request and sent as part of the evidence to OpenAI. Omitting it excludes portfolio information; recommendations never read the saved portfolio file. The separate portfolio, holdings editor and backup/restore endpoints access saved holdings; recommendation requests never do. The backend does not accept client-selected API keys, model IDs, endpoints, or arbitrary evidence. JSON day counts must be integers (not booleans, floats, or strings); unknown body fields are rejected.

HTTP history calls use `api.fetch_history(..., persist=False)`, bypassing the save function entirely. They never initialize or write the CLI database, backtest-result table, or portfolio file. The CLI retains default persistence. Analysis remains separate from persistence. The portfolio and alert endpoints described below access their own local stores; there is no user account system.

Client handling:

- 200 recommendation response: inspect `recommendation_status`. `completed` includes `recommendation`; `unavailable` includes null recommendation, a safe `ai_error`, and the computed evidence. Both provider construction and response failures are covered. There is no automatic OpenAI retry or fallback trading decision.
- 422: invalid client input. Rejected input values are not echoed.
- 429: per-process admission capacity reached. `Retry-After: 1` is advisory; clients should avoid duplicate paid requests.
- 502: failed or malformed CoinGecko data, including invalid prices. This is upstream failure, not a client validation error.
- 503: insufficient or stale history, with coverage metadata. Backend backtests and recommendations reject a latest observation more than two days old; their minimum row counts are 30 and 35 respectively.
- 500: unexpected internal failure, with a generic response and no raw exception or payload logging.

Responses use explicit models and finite JSON numbers. Zero closed backtest trades yield null win-rate and average-return values. Drawdown remains asset drawdown; strategy execution assumptions are disclosed unchanged.

`backend_service.AdmissionGate` uses a nonblocking `threading.BoundedSemaphore` and releases in `finally`. Defaults allow at most four simultaneous CoinGecko fetches and one complete recommendation operation per process. They bound concurrency, not request rate or spend, and do not coordinate across workers. Blocking routes use worker threads; `/health` is async and performs no blocking work, following the [FastAPI concurrency guidance](https://fastapi.tiangolo.com/async/). No CORS middleware is enabled.

Backend modules: `backend.py` (app factory/routes), `backend_models.py` (contracts), `backend_service.py` (orchestration/gates), and `price_validation.py` (shared numeric checks). `BackendService` accepts injected fetchers, a provider factory, and a clock for offline testing.

Install backend test dependencies and run:

```powershell
python -m pip install -r requirements-backend-dev.txt
python -m pytest tests/test_backend.py -q
```

For the entire suite, install both `requirements.txt` and `requirements-backend-dev.txt`, then run `python -m pytest -q`. Backend tests skip when optional FastAPI/HTTPX dependencies are absent. The verified environment currently emits a Starlette deprecation warning about its HTTPX TestClient compatibility path; tests still pass. Tests use mocked upstream calls; they do not spend API credits or modify the real database.

## Continuous integration

`.github/workflows/tests.yml` runs on pushes, pull requests, and manual dispatch. Its four jobs cover Windows and Ubuntu with Python 3.11 and 3.14. Each installs both CLI and backend test requirements, runs `pip check`, explicitly imports backend testing dependencies (so optional backend tests cannot silently disappear), and runs the full offline suite. Pip cache keys include all three requirement files. Jobs have a 15-minute timeout, and newer runs cancel obsolete runs for the same ref.

No provider secrets are required. `tests/conftest.py` clears OpenAI configuration for each test and blocks unmocked `requests` sessions; tests that exercise providers inject responses. This is an in-process guard for the application's HTTP client, not a general operating-system network sandbox. FastAPI's in-process HTTPX TestClient remains available.

To reproduce the test command locally:

```powershell
python -m pip install -r requirements.txt -r requirements-backend-dev.txt
python -m pip check
python -m pytest tests -q -ra --strict-markers --strict-config
```

The workflow becomes active after the workflow and all project source/tests/requirements are committed and pushed. Check results in the repository's Actions tab. Local validation does not establish that every GitHub runner job has passed; the first hosted run must confirm the matrix. Branch protection is a separate repository setting and is not enabled by this workflow.

## Local web dashboard

### Phase 1 completion (local app)

The local dashboard includes coin search, historical charts and explanations, evidence-backed AI assessments, a browser watchlist, saved portfolio valuation/editing, backup/restore, and manual price/RSI alerts. Market results appear directly under the analysis controls. Section links and responsive forms support desktop and phone-sized layouts. The service still runs locally on one worker; accounts, public hosting, a mobile binary, trained prediction models and measured prediction accuracy are outside this phase.

**Restore:** choose a portfolio JSON backup (maximum 500 KB, 100 entries), click **Preview backup**, review added/changed/removed coins and quantities, then acknowledge full replacement and click **Restore this backup**. Preview writes nothing. Restore revalidates the content and saved version, makes a `portfolio-backup-<random-id>.json` recovery copy alongside the portfolio, then atomically replaces it. Conflicts require a new preview. Empty backups clear all holdings and are shown as such. Duplicate JSON keys, invalid quantities/prices and nonfinite values are rejected. Recovery copies and downloaded backups are ignored by git. Restore a recovery copy through the same preview flow if needed. This is a holding snapshot, not transaction history or cash-flow accounting.

**Alerts:** use **Load alerts and history** to view CLI-compatible rules from `crypto_data.db` beside the modules. Create a price or RSI rule, pause/resume it, or remove it with confirmation. The first explicit alert operation lazily creates compatible alert tables if needed; server startup and market analysis do not initialize the database. Limits are 100 saved rules and 20 active rules. Exact duplicate rules are rejected. Run the CLI from the project directory to share these rules.

**Alert scheduling and semantics:** there is no automatic schedule in Phase 1. **Check alerts now** performs one check and calls CoinGecko only. Price quotes must be positive and no older than 15 minutes; RSI requires a complete 90-day UTC window and uses Wilder RSI(14). The current day may be incomplete. Above means strictly greater and below strictly less. The first matching observation triggers; later matching checks are suppressed until a valid nonmatching check rearms the rule. Unavailable data leaves the previous state intact; pausing and resuming alone does not rearm it. Checks can miss crossings between observations and are not a real-time monitoring guarantee. No email, push, background process, or OpenAI call is involved.

**Alert history:** dashboard triggers store the threshold, observed value, provider observation time and check time in a separate SQLite table. The latest 100 are displayed; at most 1,000 are retained. Removing a rule leaves its history. Existing CLI checks/log files remain separate and do not share dashboard duplicate-suppression state. Rule changes during a check are detected before recording a result. SQLite writes are transactional; concurrent check requests are bounded to one per backend process.

**Portfolio backup:** click **Download portfolio backup** to download `portfolio-backup.json` from `GET /v1/holdings/export`. This exports the saved portfolio as a CLI-compatible JSON object, including zero-quantity entries and existing metadata. It excludes unsaved editor changes and does not fetch quotes or call OpenAI. No portfolio writes occur during export. The browser controls the download location and may rename duplicate downloads. Invalid saved data produces an error instead of a downloadable backup. Backups contain private holdings; keep them outside source control. Restore is available through the preview-and-confirm flow below.

**Holding editor:** use **Load holdings editor**, select an existing coin or enter a CoinGecko ID, then enter a positive total quantity and average purchase price (0 means unknown). **Save total holding** replaces that coin's quantity and average; it is not an additional purchase or a transaction ledger. No market or AI requests run during editing. `GET /v1/holdings` returns a versioned snapshot; `PUT /v1/holdings` requires that version and returns 409 when the saved file changed. Save failures must be followed by a reload before retrying. The server writes to a temporary file, flushes it, and atomically replaces the original, preserving other holdings and metadata. Use one backend worker and avoid simultaneous CLI/file edits: browser writes are serialized in-process, not coordinated with external programs. To remove a holding, select it in the editor, click **Remove selected holding**, review its saved values, then confirm or cancel. `DELETE /v1/holdings` requires the coin ID and current version. It removes only that entry using the same atomic save path. Removal is not a sale and does not calculate realized returns. A failed or uncertain response requires a reload before retrying; there is no automatic retry or undo.

**Saved portfolio:** click **Load saved portfolio** to read `portfolio.json` beside the Python modules and request a batch of CoinGecko USD quotes by ID. Run the CLI from the project directory to use the same file. The read-only `/v1/portfolio` endpoint never changes holdings or calls OpenAI; opening the dashboard does not load the file. Missing files and zero-quantity positions produce an empty view. Invalid holdings produce a sanitized error, with no partial file import. This initial view supports up to 100 saved entries.

Quotes require a positive finite price and provider timestamp. Prices older than 15 minutes, missing quotes, and invalid quotes are excluded. Missing prices make total value and total unrealized gain/loss unavailable; a clearly labeled priced subtotal and allocation of priced holdings remain visible. Zero or omitted average purchase prices mean unknown cost basis. P&L is quantity × (quote − average purchase price), excluding fees, realized transactions and cash flows. Provider outages preserve the holding list with unavailable prices. Only IDs and quote parameters are sent to CoinGecko. Timestamp fields follow [CoinGecko's simple price API](https://docs.coingecko.com/reference/simple-price).

Run `python -m uvicorn backend:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log`, then open http://127.0.0.1:8000/. The dashboard uses local assets, without a frontend build step. Analyze fetches CoinGecko evidence; Get AI recommendation explicitly sends a fresh evidence snapshot and any enabled selected-coin position to OpenAI and may incur API charges. API credentials remain in server environment variables. No automatic requests, retries, or browser position persistence are used.

Both evidence endpoints currently show historical prices; live price is N/A. Each AI response displays its own evidence snapshot and cited values. Confidence is model judgment, not a calibrated probability. Backtest limitations and missing history remain visible.

Host must match the configured local authority. If Origin is present it must match too; non-browser clients without Origin remain supported. The default is `http://127.0.0.1:8000`. For a different port, set `CRYPTO_ORIGIN` (for example `$env:CRYPTO_ORIGIN = "http://127.0.0.1:9000"`) and launch Uvicorn on that same port. Only explicit loopback HTTP origins are accepted; localhost is supported only when explicitly configured. Tests use the matching TestClient base URL. These checks are not authentication: keep this a local single-user service, with one worker.

Dashboard interaction regressions (Node.js 22 or newer, no npm dependencies): `node tests/dashboard.test.cjs`. These run the actual browser script with a minimal DOM and mocked fetch responses; they supplement manual browser checks.

### Visual analysis

Analyze market now requests `include_history=true` on the existing analysis endpoint. The response includes chronological UTC daily price, MA7, MA25 and Bollinger (20 observations, sample standard deviation, plus/minus two standard deviations) series from the same validated historical frame used for the evidence. Warm-up values are null; missing dates are not filled. Without that query option history is empty. Recommendation evidence and OpenAI payloads do not include chart history.

The dashboard shows descriptive summaries first, then a local SVG chart with optional averages/bands, a keyboard-accessible observation slider and a data table. Exact indicators, backtest results, coverage and limitations remain under Technical details and limitations. Chart scaling follows the displayed series rather than forcing a zero baseline. Summary thresholds are descriptive conventions, not trade recommendations. Restart the backend after updating Python code, then refresh the browser.

The coin picker searches an offline starter list of eight featured assets by name, symbol or CoinGecko ID. It is not a complete or live-ranked coin catalog. Bitcoin, Ethereum and Solana have quick buttons; the editable ID field supports other assets. Filtering and selection do not fetch data or request AI. The selected name, symbol and canonical ID are shown above the analysis; custom IDs remain labeled as custom.

Click **Load full coin list** to fetch the CoinGecko catalog through `/v1/coins`. The backend caches it in memory for one hour per process, serializes refreshes, and waits 60 seconds after a failed refresh before retrying. A previous snapshot remains available with a stale flag if refresh fails. Restarting the server clears the cache. The browser searches the loaded catalog locally by name, symbol or ID and shows up to 100 matches at a time; refine the search to find more specific entries. Duplicate symbols remain distinguishable by ID. Entries with IDs unsupported by the existing analysis slug contract are omitted. Listing does not imply sufficient historical data. No OpenAI calls are made by catalog loading or search.

## Stock and ETF research

The dashboard now includes a separate US stock/ETF research section using Twelve Data. See [Phase 2 setup and operating guide](PHASE2_COMPLETION.md) for key setup, session-aware charts, data coverage, licensing limitations and what remains crypto-specific. Live acceptance is pending a user-owned provider key.

## Dashboard pages

The shared navigation opens six independent pages: Market (`/`), Stocks & ETFs (`/stocks.html`), Watchlist (`/watchlist.html`), Portfolio (`/portfolio.html`), Backups (`/backups.html`), and Alerts (`/alerts.html`). The current page is highlighted. Portfolio includes valuation and the holding editor; Backups includes export and confirmed restore. Watchlist entries link to the selected coin on Market without automatically requesting analysis or AI. Saved watchlists continue to use the same browser-storage key. Each page loads only its own controls and shared helpers.

## Research datasets (Phase 3)

Use `dataset_cli.py` to capture versioned crypto/stock/ETF snapshots and build reproducible, causal features with separate forward-return labels. Optional benchmark context and missing-session checks are included. See [the dataset operating guide](PHASE3_DATASETS.md) for commands, quality rules and historical-data limitations. Training and evaluation follow in Phase 4; no accuracy claims are generated here.
# Current research milestone

The stock/ETF workspace now includes interactive history navigation, optional genuine daily OHLC candlesticks, volume and explained Advanced tables. Phase 4 covers a fixed ten-asset universe, yearly baseline evaluation and an append-only manual prediction journal. The model has not passed the recommendation promotion gate.

- [Phase 4 completion and operating instructions](PHASE4_COMPLETION.md)
- [Every expanded asset/year result](PHASE4_EXPANDED_RESULTS.md)
- [UI polish](UI_POLISH.md)
- [Fresh-data issuance attempt](PROSPECTIVE_START.md)
- [Hosted app and licensing plan](APP_RELEASE_PLAN.md)

The hosted app is planned, not deployed. Current operation remains a single-user loopback-only local application. Earlier phase-specific sections describe the capabilities at those milestones.

## Phase 5 account staging

Phase 8 step 1 improves listing filters and adds explicit, bounded interactive history caching with fresh-fetch controls. Research capture still bypasses the browsing cache. See [the discovery and history reliability guide](PHASE8_DISCOVERY.md).

Phase 6/7 follow-up adds read-only prospective validation reports and an explicit, evidence-linked stock/ETF/crypto assessment flow in the account research app. See [the implementation and operating guide](PHASE6_7_COMPLETION.md) for request privacy, run commands, tests and outstanding validation/visual checks.

The account workspace now includes explicit stock/ETF and crypto research, shared interactive charts and selected-stock watchlist saving. See [the product research completion guide](PRODUCT_RESEARCH_COMPLETION.md) for synthetic staging, private live research, the prospective prediction batch and verification limits.

A separate account factory adds managed OIDC integration, per-user server storage, revision-safe edits, explicit import previews and account exports. Try the loopback-only sample profiles using the [Phase 5 guide](PHASE5_COMPLETION.md). The original local research app remains on its own factory. Real hosted identity/database setup and market-display licensing are pending; the sample profiles must not be publicly exposed.

See [Phase 8 local milestone](PHASE8_MILESTONE.md) for delivered features, validation and remaining release limits.

See [Discovery and simplified research release](DISCOVERY_RELEASE.md) for the latest browsing and usability improvements.
