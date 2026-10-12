# Phase 2 implementation — US stock and ETF research

Implemented locally on 2026-09-28. Live IBM and SPY history requests succeeded on 2026-09-30 using the user-configured server key. Both returned 61 observations through September 29; the expected September 30 session was unavailable, so indicators were correctly withheld. No paid OpenAI request was made. Changes are not committed or published.

## What the dashboard adds

Use **Stocks & ETFs** in the navigation to open the separate `/stocks.html` research page. Choose Stocks or ETFs, click **Load supported listings**, search by name, symbol or exchange, and select a listing from the dropdown. The dropdown includes every matching supported listing, sorted by company/fund name, with ticker and exchange alongside it. Search is optional; no ticker knowledge is required. This is not a claim to include every stock worldwide.

Click **Research selected listing** to fetch daily history. The default window is 90 calendar days; 35–365 are accepted. The chart shows closing prices, optional 7/25-observation averages and 20-observation Bollinger Bands. The slider and expandable data table expose exact values. RSI, MACD and moving averages have plain-language descriptions and exact values.

At least 35 completed trading observations and complete coverage are required for indicators. A 35-calendar-day window usually has fewer than 35 sessions, so try 90 days. Incomplete history is shown with missing session dates and no indicators; nothing is filled or silently substituted. Weekends and market holidays are not missing observations. The calendar includes shortened regular sessions, excludes extended hours and excludes today's session until its scheduled close. A just-closed bar can still be delayed by the provider.

The chart connects consecutive trading sessions over weekends and holidays, but breaks at missing expected sessions. Dates are exchange session dates, not midnight UTC timestamps. Only US USD listings on explicitly supported MICs are accepted: XNYS, XNAS, XNGS, XNMS, XNCM, ARCX, XASE and BATS. Nasdaq segment MICs are preserved rather than rewritten to XNAS. They use the XNYS regular-session calendar in exchange-calendars 4.13.2.

## Setup

Create your own Twelve Data account and key using the provider's website. Do not paste the key into chat or commit it. In the same PowerShell session used to launch the app:

```powershell
cd C:\Users\sergi\OneDrive\Desktop\Python\Projects\Crypto
.\.venv\Scripts\python.exe -m pip install -r requirements-backend.txt
$env:TWELVE_DATA_API_KEY = Read-Host 'Twelve Data API key' -MaskInput
.\.venv\Scripts\python.exe -m uvicorn backend:create_app --factory --host 127.0.0.1 --port 8000
```

`-MaskInput` requires PowerShell 7.1+. The environment variable lasts for this process and its children; set it again in a new terminal. Open http://127.0.0.1:8000. The key stays on the backend and is sent only in Twelve Data's authorization header, never in browser requests or query strings. No key is required to start the app or use crypto features.

Basic currently advertises 8 API credits/minute and 800/day. Catalog inclusion does not guarantee history entitlement. The adapter uses explicit actions, a daily in-memory catalog cache and a one-minute catalog failure backoff; historical requests are not cached or retried automatically. Quotas are shared with other uses of your account and are enforced by the provider.

Licensing needs a separate acceptance check: the pricing page labels Basic as internal non-display, while the provider's usage guide permits non-production development/testing on individual plans. Do not infer public dashboard/mobile redistribution rights from having a key or a successful response. Confirm the intended display use with the provider before live deployment; no paid plan was selected or purchased.

## Data identity and reliability

`assets.py` defines provider-qualified IDs including asset class, exchange MIC, currency and provider symbol. For example `twelvedata:stock:XNGS:USD:AAPL` cannot collide with a different exchange listing or a crypto ID. CoinGecko uses its canonical coin ID instead of its ambiguous display ticker. Existing crypto storage and routes remain compatible.

The adapter checks returned symbol, MIC, currency, interval and exchange timezone. It rejects duplicate/invalid dates, nonfinite/negative prices, inconsistent OHLC values, invalid volume, and bars on non-trading days. Transport failures, rejected keys, quotas and invalid payloads produce sanitized errors. Redirects are disabled to avoid forwarding authorization to another endpoint.

Daily history explicitly requests `adjust=splits`. This is split-adjusted price history, not dividend-inclusive total return. The current provider catalog is not a permanent security master: ticker reuse, mergers, historic identifier changes and delisted coverage are not resolved. Point-in-time corporate-action archives are deferred to dataset work; this data must not be treated as a survivorship-bias-free training universe.

## Reusable API and modules

- `GET /v1/assets?asset_class=crypto|stock|etf`: shared listing identity with cache freshness and coverage information.
- `GET /v1/stock-analysis?asset_id=...&days=90`: completed-session history, OHLCV bars, coverage, indicators and limitations.
- `stock_provider.py`: transport, account errors and provider validation.
- `stock_service.py`: cached discovery and session-aware analysis.
- `stock_models.py`: typed API response contracts.
- `static/assets/stocks.js`: explicit dashboard interactions and stale-response protection.

Changing asset type, search, selection or window clears old stock results. An old response is discarded if the selection changed while it was loading. Opening the page, typing or changing the dropdown does not initiate a provider request.

## Scope boundaries

The current saved portfolio, watchlist, alerts, backtests and OpenAI recommendations remain crypto-specific. Stock research neither modifies that storage nor sends stock data to OpenAI. Cross-asset portfolios require a deliberate storage migration. No prediction model, future-price target or accuracy percentage is produced by this phase.

Next: Phase 3 adds versioned historical datasets and causal features; Phase 4 trains/evaluates baselines chronologically; Phase 5 combines validated model outputs with AI explanations; Phase 6 tracks models/predictions/outcomes; Phase 7 addresses accounts, jobs, licensing, deployment and mobile.

## Provider references

Verification: 340 Python tests passed with strict marker/configuration checks and live HTTP blocked. 47 dashboard tests passed. The runtime virtual environment passes `pip check`. Browser QA used synthetic stock/ETF data: discovery, chart, keyboard observation slider, asset-type invalidation and a 390px layout with no horizontal overflow. No user database or saved holdings were used in these checks. Two existing dependency deprecation warnings remain (Starlette/httpx and AnyIO); no tests were skipped. Hosted Windows/Linux CI and live provider entitlements have not yet been verified for this change.

- https://twelvedata.com/docs
- https://twelvedata.com/pricing
- https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage
- https://support.twelvedata.com/en/articles/5179064-are-the-prices-adjusted
- https://github.com/gerrymanoim/exchange_calendars

## Live acceptance follow-up — 2026-09-30

The running app returned 3,097 supported stock listings and 8,503 ETFs before the Nasdaq segment fix. IBM (XNYS) and SPY (ARCX) each returned 61 of 62 expected sessions in the July 3–September 30 window, with September 30 missing. Their latest bars were September 29; indicators remained unavailable by design. This verifies live transport and partial-coverage behavior, not complete-window indicator acceptance or independent price accuracy.

A public provider catalog showed AAPL, MSFT and NVDA use XNGS. Added XNGS/XNMS/XNCM to the shared supported-MIC set and regression-tested discovery and exact-MIC history requests. All 30 stock tests pass. The user must restart the server to load this change; live Nasdaq history remains unverified. Catalog requests now allow 45-second read timeouts after a live catalog download exceeded the former 15-second limit. No key was read, displayed, or written to project files.

## Separate research pages

Crypto stays on `/`; stock and ETF research now lives on `/stocks.html`, linked in both directions. Both pages load common formatting and request helpers, while the stock page does not initialize crypto controls. Opening either page makes no provider requests automatically. Click **Load company / fund list**, choose a name from the alphabetical dropdown, then click **Research selected listing**. All supported matches are included; the former 200-result display cap is removed.
