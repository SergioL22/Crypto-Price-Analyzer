# Product research and prospective validation — October 13, 2026

The account foundation now has a usable research panel. Real identity-provider accounts and hosted staging remain deferred until the launch preparation stage.

## Research workspace

- Load stock or ETF listings explicitly, search company/fund names or symbols, and filter by supported US exchange MIC. Filtering reuses the loaded catalog. Catalog inclusion does not guarantee that the current provider subscription supplies history.
- Choose three months, one year, five years or ten years of stock/ETF history. Completed exchange sessions determine coverage; gaps remain visible and prevent indicator claims.
- See a prominent latest historical price, its date, the change across the selected history, and interactive chart navigation. Genuine stock OHLC supports candles and share volume; crypto daily samples do not invent candles.
- See plain-language trend, RSI and MACD explanations. Exact values, chart tables and coverage stay collapsed until opened. The complete chart data table is built on first opening, avoiding thousands of hidden rows during initial display.
- Save the selected stock/ETF to the signed-in account watchlist, then use its portfolio and saved-rule editors. Crypto is research-only in this account app and offers three explicitly labeled starter coins.
- Sample account analysis uses synthetic data. A separate, explicit private factory uses Twelve Data/CoinGecko history and reads the ignored local environment configuration. Neither mode automatically requests analysis or OpenAI recommendations. Saved alert rules are not actively monitored here.

Research reads require a session, are throttled by account, and share a bounded admission gate. Provider failures return sanitized messages. Selection changes/sign-out discard late responses. Reload refreshes identity and rejects a workspace returned for a different account. Managed deployments default to disabled market data, and cannot enable the private live adapter; hosted licensing/identity acceptance remain separate work.

## Run locally

From the project directory, choose one factory:

```powershell
# Synthetic data, no provider calls
.\.venv\Scripts\python.exe -m uvicorn account_backend:create_staging_app --factory --host 127.0.0.1 --port 8001 --workers 1 --no-access-log --no-proxy-headers
```

```powershell
# Explicit private provider history; uses your existing ignored .env
.\.venv\Scripts\python.exe -m uvicorn account_backend:create_local_research_app --factory --host 127.0.0.1 --port 8001 --workers 1 --no-access-log --no-proxy-headers
```

Open http://127.0.0.1:8001/ and choose Avery or Sam. These are sample identities, even in private live research mode: anyone on the local machine can open them. Use synthetic positions only. Never expose either factory publicly or reverse-proxy it. Only run one on port 8001; stop it with Ctrl+C. The original app on port 8000 remains separate.

## Prospective validation

Fresh complete ten-year captures successfully issued ten predictions for MSFT, JNJ, JPM, XOM, QQQ, IWM, DIA, AAPL, IBM and SPY. The source session is October 12. Their five target sessions are October 13, 14, 15, 16 and 19.

There are ten pending predictions and zero completed outcomes. No accuracy, calibration or model promotion is claimed. After the October 19 close and provider publication, capture fresh outcome history and use the existing manual settlement command for each matching prediction/snapshot. Identity, target completion, complete outcome coverage and unchanged origin prices must pass validation. A quiet daily follow-up at 6 p.m. America/Chicago is now scheduled. It waits until the October 19 close before requesting outcome history, uses the existing settlement gates, reports meaningful results or failures, and pauses after all ten outcomes are summarized. The desktop app and this local checkout must be available for the follow-up to run.

```powershell
.\.venv\Scripts\python.exe phase4_cli.py journal
.\.venv\Scripts\python.exe phase4_cli.py settle --prediction PREDICTION_ID --snapshot NEW_OUTCOME_SNAPSHOT_ID
```

See PROSPECTIVE_START.md for the earlier withheld attempt and the successful retry. Runtime datasets and journal databases remain ignored; keep them locally for subsequent scoring.

## Verification and limits

- Full offline suite: 427 Python tests and 100 frontend tests passed. New cases cover authenticated research, synthetic stock/ETF/crypto history, completed UTC boundaries, gaps, read-only crypto fetching, provider failure recovery, stale responses, crypto save exclusion and account switching.
- Live protected-route acceptance: 7,575 stock listings; MSFT returned 62 complete trading sessions in a 90-day calendar window, latest session October 12, with indicators available.
- Synthetic ten-year performance sample: 2,512 observations processed in 0.392 seconds, with about 1 MB of JSON. This measures adapter processing on this machine, not phone rendering or production throughput.
- Responsive styles stack forms/signals at narrow widths and contain wide tables. Browser access to the local preview was rejected by the browser tool, so rendered desktop/mobile visual QA is still pending. This limitation is not represented as a completed visual test.
- Real sign-in, hosted databases, deployment, provider display licensing and reliable predictive accuracy remain unverified. This is local product/test progress, not public-release approval.

This guide accompanies the product research milestone. Rendered visual acceptance remains outstanding; published source and automated tests do not establish a completed mobile usability check.
