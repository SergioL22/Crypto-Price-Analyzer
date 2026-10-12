# Phase 1 completion — 2026-09-27

The local, single-user research dashboard is feature-complete for Phase 1. This is not a public deployment or a trained price-prediction product.

## Delivered across Phase 1

- Searchable CoinGecko catalog with an in-memory cache, dropdown, quick choices and manual ID fallback.
- Historical price chart, moving averages, Bollinger overlays, observation inspection and exact evidence tables.
- Plain-language indicator explanations and backtest limitations. AI assessments remain explicit requests with their own cited evidence; model confidence is not prediction accuracy.
- Browser-local watchlists with duplicate/size limits and storage-error handling.
- Portfolio valuation with per-coin quote timestamps, missing/stale-price handling, allocation bars and unrealized gain/loss when cost basis is known. Very small prices and quantities remain visible rather than rounding to zero.
- Add/update/remove holdings from the dashboard. Saves set total quantities, preserve other entries, use atomic replacement and reject stale editor versions. Removal shows the saved entry before confirmation.
- JSON backup downloads. Restore previews added, changed and removed coins, requires explicit full-replacement acknowledgment, rejects malformed/duplicate-key/oversized backups, checks the saved version and writes an automatic recovery copy before replacement.
- CLI-compatible price and Wilder RSI alerts with creation, pause/resume and confirmed removal. Checks are manual. Recent quotes/history are required; unavailable data does not clear suppression state. Repeated matching observations do not repeatedly trigger; a valid nonmatch rearms the rule.
- Persistent dashboard alert history: observed values, thresholds, source timestamps and check times. Latest 100 displayed, up to 1,000 retained. Removal preserves history; CLI log behavior stays separate.
- Desktop/phone layouts, section navigation and market results placed immediately below the market controls.
- Offline Python and JavaScript regression coverage, with existing Windows/Linux CI configuration retained.

## Validation

- 314 Python tests pass, including strict marker/configuration checks. Network-provider requests are blocked in tests.
- 43 dependency-free JavaScript dashboard tests pass.
- The project runtime virtual environment passes `pip check` and backend startup (14 API paths). It does not contain pytest; the full Python test run used the installed system test environment. A temporary test launcher only adjusted Windows test-directory ACL inheritance for this sandbox.
- Browser verified with sample data: chart/explanations, failed catalog fallback, watchlist persistence across reload, AI unavailable with evidence retained, replacement preview, first alert trigger and repeated-check suppression, and history display.
- Desktop and 390px-wide phone views inspected; no horizontal page overflow. Storage-denial, malformed responses, stale requests and provider failures were tested with mocks.
- Real portfolio/database data was not used or changed for these checks. No live OpenAI call or paid API test was run. Live provider availability and hosted CI are not established by these tests.

## Run

From the Crypto project directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open http://127.0.0.1:8000. Restart the server and refresh the page after updating. Load data and run checks explicitly; nothing starts monitoring in the background.

## Operational limits

Keep the server on loopback with one worker. Host/Origin checks are not account authentication. Avoid concurrent CLI/manual edits of portfolio.json; external programs do not share the dashboard's in-process lock. Backups contain private holdings and are excluded from git. Restoring replaces the complete snapshot; it does not merge trades or reconstruct transaction history.

Price alert data must be at most 15 minutes old. RSI requires the complete requested 90-day daily window, including a potentially incomplete current UTC day. Checks can miss moves between observations. Up to 20 active rules and 100 saved rules are supported. No scheduled worker, email or push delivery is included.

Stocks/ETFs, transaction/cash-flow accounting, trained forecasting models, measured out-of-sample accuracy, accounts, public deployment and a mobile app remain later phases.

## Release status

Local changes are not committed or pushed. The next release step is to commit the reviewed source/tests/docs (excluding portfolio files, recovery backups and runtime databases), push, and verify all hosted CI jobs. No hosted CI success is claimed for this revision.
