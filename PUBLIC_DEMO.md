# Public synthetic research demo

This is a separate anonymous demonstration, not a public release of provider data. It contains five fictional companies and three fictional funds with deterministic generated OHLC/volume series, using US session dates only as a calendar. Data is identified with a `demo:` asset namespace, provider `demo`, adjustment `synthetic`, a synthetic response header, page banner, chart/result labels and source disclosures. No real business profiles, live market returns or measured predictive accuracy are presented.

## Separation and guarantees

`public_demo:create_app` always constructs `SyntheticProvider` and `SyntheticProfiles`. It accepts no live provider injection or environment switch and never loads local `.env`. Existing provider keys in the environment do not change the source. Tests block construction of live transports and normal offline tests block network calls. There are no account, private holdings, Crypto, prediction journal or paid LLM routes. Only packaged stock UI pages and assets, catalog, synthetic stock research, synthetic-profile-unavailable response and a data-free health check are served.

`hosted_preview:create_app` and its existing `render.yaml` remain password protected. The public demo uses `Dockerfile.demo` and **render-demo.yaml**, with a new **research-desk-demo** service. No credentials or database are requested. Do not change the existing private Blueprint path or replace its service with the demo.

Demo browser storage uses `research-desk.demo.equities.v1` and a separate monitoring lease. Private and demo asset IDs are rejected in the opposite local workspace. On separate Render domains, browser origin isolation also separates stored state. Demo backups contain fictional data and are not meant to be imported into the real account API. Browser storage is local to the device/site and can be cleared; no server sync is implied.

## Try locally

Use a separate terminal and port:

```powershell
$env:PUBLIC_DEMO_ORIGIN = 'http://127.0.0.1:8002'
.\.venv\Scripts\python.exe -m uvicorn public_demo:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

No key is needed. Open the local address, choose a fictional listing, save it to the demo watchlist and try the simulator/comparison. Dates can span up to 3660 days. Prices are anchored to a fixed formula epoch, so overlapping captures are reproducible. No capture or model-prediction record is created.

## Deploy as a separate free service

1. Publish this reviewed commit and confirm all seven CI jobs pass. The existing container job now builds and smoke-tests both private and public images. The public image must boot with no credentials, serve an anonymous banner and generated research, and reject private routes.
2. In Render choose **New → Blueprint** and connect `SergioL22/Crypto-Price-Analyzer` on `main`.
3. Name the new Blueprint **research-desk-demo**. Set **Blueprint Path** to **render-demo.yaml**, not render.yaml.
4. Review that it creates exactly one NEW **research-desk-demo**, Docker, **Free** service, with Dockerfile.demo and no database, API-key fields or password prompts. Stop if the page proposes changing the private service or charging for a plan.
5. Deploy the new Blueprint. Render supplies its external URL; the demo validates that exact HTTPS origin. A custom domain later requires explicitly setting PUBLIC_DEMO_ORIGIN without a trailing slash.
6. After Live, open the demo URL in a private browser window. It should not ask for credentials. Confirm the synthetic banner, fictional listings, chart, watchlist, simulator and comparison. Share the URL for a final read-only check; no secrets are needed.

Official Render setup supports a custom Blueprint Path: https://render.com/docs/infrastructure-as-code .

Render Free services sleep and share the workspace's monthly free-instance allowance (currently 750 hours), bandwidth and build limits. A second Free service does not provide a second independent allowance. Monitor the existing workspace limits; do not automatically upgrade or add paid resources. See https://render.com/docs/free .

## Operational limits

The demo uses a global 120-request/minute in-memory budget, two concurrent market operations, bounded history caching and a 3660-day parameter ceiling. This protects a small preview from unbounded work; it is not durable per-visitor production enforcement. Cache/budget state can reset on a free-service restart, but there are no upstream provider credits or AI charges to exhaust. No external requests are needed for synthetic generation. It is still subject to Render's hosting/usage limits and cold starts.

Headers restrict scripts, styles and connections to the same origin. Wrong hosts/origins and write methods are rejected. Private files and endpoint routes are absent. There is no automatic real-data fallback if a fictional listing is unavailable.

## Verification

567 Python and 171 frontend tests passed. Checks cover anonymous access, labels, deterministic prefix stability, distinct series, OHLC consistency, no live-provider constructors even when test keys are present, no database creation, rejected real asset IDs, absent private/paid routes, unchanged private sign-in and demo storage separation. An anonymous local browser check loaded a fictional stock, saved it and completed a synthetic investment scenario. Docker is unavailable locally; CI container checks must pass before the hosted demo is considered ready. The service is not considered deployed until its actual Render URL is verified.

Prediction scoring remains separate and pending until the October 19, 2026 target session closes. This demo does not score or promote any model or display real prediction accuracy. Public use of real provider data remains subject to the separate permissions and quota requirements.
