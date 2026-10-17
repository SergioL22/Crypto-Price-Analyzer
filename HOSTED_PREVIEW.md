# Private Render preview

This is a private, password-protected stock/ETF research preview. The local server and real-account server remain separate. It supports discovery, stock analysis, company profiles (optional key), browser-local watchlists, foreground monitoring, comparisons and the hypothetical investment simulator. It does not expose local databases, saved server portfolios, crypto APIs, account APIs, prediction journals or recommendation/LLM endpoints. It creates no account database.

## Deploy

1. Publish the reviewed commit and confirm all seven GitHub Actions jobs pass, including **Hosted preview / container**. Docker is not available in the local Windows session; the Linux CI container build/start test is a required release check.
2. In Render, choose **New → Blueprint**, connect only the intended GitHub repository `SergioL22/Crypto-Price-Analyzer`, and use `main` with `render.yaml`. Review any GitHub repository-permission prompt yourself. The recipe creates one **Free** Docker web service and no database or disk. Do not select a paid instance.
3. Enter your Twelve Data key in Render's private prompt for `TWELVE_DATA_API_KEY`. Never put keys in source, chat, screenshots or the build command. For optional company profiles, add `FINNHUB_API_KEY` under the service's Environment settings after creation. Do not add OpenAI or personal account credentials; this preview does not use them.
4. Render generates `HOSTED_PREVIEW_PASSWORD`. After the deploy is Live, open Environment, reveal/copy that value privately and keep it in your password manager. Open the service HTTPS URL and sign in to the browser prompt with username **preview** and that password. This is a shared preview gate, not individual user accounts. To revoke a shared password, change it in Render and redeploy. Browsers may retain Basic authentication for the session; close the browser session when finished.
5. Render supplies `RENDER_EXTERNAL_URL`; it becomes the exact allowed HTTPS origin. If using a custom domain later, explicitly set `HOSTED_ORIGIN` to its origin without a trailing slash. No wildcard origins are accepted.
6. Share only the non-secret service URL for verification. Do not share the password or keys here.

## Runtime and persistence

The image runs as a non-root user on `$PORT`, with exactly one Uvicorn worker. Render must be the sole ingress: its TLS proxy supplies the trusted forwarded scheme. Do not reuse the wildcard forwarded-proxy command on an independently exposed server. Every route except data-free `/health` requires authentication. Wrong hosts, HTTP, cross-origin requests and write methods are rejected. Stock/provider errors are sanitized. The service has a global request window, two concurrent market operations, and existing history/profile provider budgets and caches. These controls are per process, not distributed: keep one instance/worker for this preview. No paid AI calls are possible through this entry point.

Render's Free web service sleeps after 15 minutes without inbound traffic and wakes on the next request. Its filesystem is ephemeral, so caches reset on a restart/deploy. No server-side user persistence is advertised or required. Watchlists, tracking dates, manual scenarios and rules remain in each browser at the hosted origin. They do not automatically transfer from localhost or synchronize across devices. Use the existing browser backup/export and restore controls if you want to transfer your own workspace. Clearing browser data removes those local items.

A free provider key remains subject to its own quotas, venue coverage and usage terms. This is a private preview, not an unrestricted public market-data service or a production account launch. Monitoring remains foreground-only and uses completed-session closes. Phone browsers can visit the HTTPS site, but each browser has its own workspace.

The Docker build explicitly copies runtime source and static assets, not `.env`, database, log, portfolio, journal or model-capture files. Render secrets are injected at runtime, not build arguments. Do not upload the project folder as a zip containing local runtime files.

## Verify after deploy

- `/health` returns `{"status":"ok"}`; opening the root anonymously prompts for sign-in.
- Correct preview credentials open Stocks & ETFs and the preview banner.
- Select a listing and confirm its price/date and chart. The provider may take time or reject quotas; errors must be visible without retries.
- Save a listing, open Watchlist, and run a hypothetical calculation from Investment Simulator. Missing coverage must not be invented.
- `/v1/holdings`, `/v1/portfolio`, `/account.html`, `/crypto.html` and `/v1/recommendations` return 404 after sign-in.
- Company details require the optional Finnhub key; missing setup does not disable stock analysis.

Local verification uses sample data and synthetic credentials only. A successful local test run is not confirmation of a successful Render deploy or provider entitlement; verify the actual service before calling it hosted.

Official sources: https://render.com/docs/free , https://render.com/docs/docker , https://render.com/docs/blueprint-spec .
