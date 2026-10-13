# App release plan

## Direction

Keep the current release a single-user local research application while preparing a hosted web/PWA release. A responsive web app should be the first public client; a native mobile client can later use the same versioned backend. Stocks and ETFs remain the home workspace, with Crypto as the secondary market. This plan does not deploy the server, create accounts, subscribe to services or purchase licenses.

## Hosting and account architecture

The future hosted service should separate frontend assets, authenticated API, provider adapters, account data and research artifacts. Run the API behind HTTPS with a managed PostgreSQL database and a separate worker for bounded jobs. Keep the existing loopback-only local factory until the hosted mode has its own authentication, ownership checks, rate limits and deployment tests. Do not expose the current local server or filesystem-backed endpoints directly to the internet.

Use a managed identity provider for registration, sign-in, verified email, recovery and session management. Provider choice and recurring hosting costs remain decisions before provisioning. Prefer secure HttpOnly/SameSite session cookies for the first-party web client, CSRF protection for writes, restricted origins and authenticated API access for mobile. Enforce user ownership on every watchlist, holding, alert, backup and journal lookup; a user-supplied asset ID is not authorization. Test attempts to access another user's data explicitly.

## Secure data and migration

Keep market-provider and LLM credentials on the server using the hosting platform's secret store; never ship shared keys to a browser or mobile bundle. Separate account data from public market caches and immutable research artifacts. Encrypt transport and use encrypted managed storage/backups, with restore drills, retention rules, export and deletion flows. Logs should redact credentials and private positions; provider diagnostics should remain sanitized.

Replace browser/local account storage with user-owned database records and optimistic concurrency checks. Migrate by previewing an import, confirming its destination account and applying it transactionally. Keep the current local backup format as a migration input; do not automatically upload a user's existing holdings. Journal predictions/outcomes retain append-only identities and timestamps. Include implementation/model versions when outputs change.

## Provider transition and licensing

The current free provider adapter remains useful for local development. Public display is a separate entitlement decision, not merely a higher rate limit. Twelve Data's individual plans are described as personal/internal/non-production usage; business commercial display remains subject to exchange licensing, and redistribution requires a separate agreement. Confirm the rights for the exact assets, audience, geography, caching and derived outputs with the provider before public rollout. Sources checked October 12, 2026: [commercial/personal usage](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage), [terms](https://twelvedata.com/terms), [business plans](https://twelvedata.com/pricing-business).

For Crypto, verify attribution and storage/display/redistribution permissions for the chosen CoinGecko plan. Raw-data redistribution is restricted; a commercial license does not automatically grant reseller rights. Sources: [API terms](https://www.coingecko.com/en/api_terms), [commercial/custom licenses](https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses).

Keep the transition behind the existing provider interface. Add an explicit capability configuration (supported markets, history, fundamentals, timestamps and permitted display use) and account-level quotas. Upgrading changes entitlement/configuration, not the UI's asset identities or analysis formulas. Contract tests must verify that paid adapters preserve units, adjustment basis and session semantics. Do not silently substitute another data source or change return definitions when an entitlement is missing.

## Predictions and AI

The retrospective stock model did not establish a consistent advantage over always-up yearly baselines. Keep it research-only. Begin fresh predictions only with complete current data; outcomes become available after five exchange sessions. No automatic collector or paid AI call is part of this release plan. Never label a model's self-rated confidence as historical accuracy or calibrated probability.

Before prediction-driven recommendations, review sufficient prospective samples, matched baselines, probability calibration, asset/regime stability and uncertainty. Present the horizon, sample size, evaluation period, freshness and model version with any eventual performance number. Add user-visible consent for sending positions to an LLM, per-user spend/rate limits, and failure states that preserve the raw analysis. Do not add order execution as part of this research app release.

## Implementation order and release acceptance

1. Publish the local milestone and confirm all six existing CI matrix jobs pass.
2. Continue manual fresh-data capture, journal issuance and later outcome scoring; keep pending results explicit.
3. Choose licensing/hosting/identity vendors and budget before paid provisioning.
4. Implement authenticated account storage and import previews in an isolated hosted mode, with ownership and concurrency tests.
5. Add bounded provider/AI quotas, secrets management, redacted logs, backup/restore and accessibility checks.
6. Deploy an authenticated staging web app with synthetic data first; test phone layouts, cross-account isolation, session expiry and recovery.
7. Enable licensed market data only after entitlement approval; release a small beta with clear research limitations and cost monitoring.

Public-release acceptance requires passing CI, access isolation, no client-side shared credentials, reliable data timestamps, licensed display rights, tested recovery and a documented support/rollback process. Passing the historical model tests alone is not a prediction-release gate.
