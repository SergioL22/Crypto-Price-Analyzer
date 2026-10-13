# Phase 5 account foundation and private staging

Phase 5's account implementation and local staging checks are complete. A separate account application now supports managed sign-in integration, per-user workspace storage, revision-safe edits, explicit migration previews and account backups. The original local research app remains separate. A real identity tenant, managed PostgreSQL service, domain and hosted deployment have not been provisioned or tested; this is not a public-release approval.

## Try the private sample staging app

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-accounts.txt
.\.venv\Scripts\python.exe -m uvicorn account_backend:create_staging_app --factory --host 127.0.0.1 --port 8001 --workers 1 --no-access-log --no-proxy-headers
```

Open `http://127.0.0.1:8001/`. This is separate from the original app on port 8000. Stop it with Ctrl+C. If the port is occupied, stop only your previously started staging process rather than changing the origin or exposing it publicly.

Avery and Sam are visibly labeled sample profiles, not password authentication. Use synthetic data only: anyone on your local machine who opens a sample profile can access that profile. Both the origin and the source client address must be loopback; forged Host/Origin headers from a remote client do not enable the sample login. Do not reverse-proxy this factory into a public site. There are no market-provider, LLM, live pricing or automatic alert-check requests in this mode.

The new sample account database is `accounts-staging.db`, ignored with its sidecars. The original crypto database, stock browser storage, portfolio files, research datasets and prediction journal are not read or rewritten by this app. Browser QA created synthetic watchlists, positions and rules for the sample profiles, so they may already contain examples on this machine.

## What the user can do

- Open a sample account, save a sample watchlist, record/update/remove positions and save/remove price or RSI rules.
- Reload server-side data or sign out. Private list content, selectors, draft values and import state are cleared on sign-out or an unauthorized response.
- Choose an existing stock/ETF workspace backup file. No localStorage scan or automatic upload occurs. Press Preview import to upload the selected file for validation; inspect the destination account, original/incoming counts, listing names, positions/costs and rule thresholds.
- Explicitly acknowledge replacement before Confirm import. Confirmation replaces that account's complete workspace transactionally. It does not change the original file or local app.
- Cancel a preview, or download an account backup compatible with the stock workspace's version-1 format. Crypto and research/journal backup formats are separate and are not imported by this flow.

Saved alert rules are not monitoring activity. Saved positions are not live valuations. Existing licensed market analysis, AI recommendations and prediction outcomes remain separate; none were enabled in the account factory.

## Identity and authorization

The HTTPS factory is `account_backend:create_app`. It fails closed if its origin, database, strong state-signing secret or OpenID provider settings are absent. It has no sample-login fallback. Its managed provider adapter uses authorization-code flow with PKCE S256, signed ID-token validation, state/nonce, audience, expiry and configured issuer checks through Authlib. It requires `email_verified: true`; providers without that verified claim are rejected. Configure registration, email verification, MFA/recovery and consent at the identity provider. The app never stores a password, access token or ID token, and does not merge identities by email.

Accounts are identified by `(issuer, subject)` and assigned an internal random ID. Every workspace operation derives its owner from the server session; bodies cannot select another owner. Import tokens are random, hashed in storage, bound to the account and issuing session, expire after ten minutes, and are consumed exactly once. Cancellation revokes the preview. A stale workspace revision rejects confirmation rather than replacing newer data.

Sessions use random opaque cookies, with only token hashes stored in the database. The HTTPS cookie uses the `__Host-` prefix, HttpOnly, Secure, SameSite=Lax and an eight-hour expiry. Logout revokes the session and its import previews. Same-origin checks and a per-session CSRF header protect mutations. A separate short-lived signed cookie stores transient OIDC state; provider tokens are not put in either cookie. API and static responses use no-store, CSP, anti-framing and no-sniff headers; production mode also emits HSTS. HTTPS is required after trusted proxy processing.

Bodies are bounded at 500 KB, with bounded arrays, validated asset IDs, finite numeric values and sanitized error responses. Atomic database counters limit login/preview/write requests. RequestValidation errors do not echo rejected holdings or credentials. Provider diagnostics are sanitized, and operating instructions disable access logs so authorization codes are not logged in callback URLs. Deployment ingress logs require equivalent redaction.

## Storage and concurrency

SQLAlchemy separates account, session, workspace, preview and throttling tables. Workspaces retain the existing version-1 shape with an account-owned revision number. Update statements condition on both owner and revision; concurrent edits cannot overwrite a winner silently. SQLite staging uses immediate writer transactions for read/modify/write operations. Database constraints and transaction rollback protect account creation and preview confirmation. State is shared through the database rather than relying on process-local account dictionaries.

The same table definitions support a PostgreSQL SQLAlchemy URL. Install `requirements-accounts-postgres.txt` for the driver and configure TLS verification per your managed provider. A real PostgreSQL deployment, backup restoration, tenant credentials, managed encryption and schema migration procedure still require acceptance checks before public use. Startup creates initial tables; it is not a general schema-upgrade/migration engine. Back up the account database with the database's consistent backup tools while avoiding partial copies during writes.

## Hosted configuration

Set these values in your deployment's server-side secret/configuration store; do not send secrets to the browser or commit them:

| Variable | Purpose |
|---|---|
| `ACCOUNTS_ORIGIN` | Exact HTTPS origin, without path or trailing slash |
| `ACCOUNTS_DATABASE_URL` | Separate account database connection URL |
| `ACCOUNTS_STATE_SECRET` | High-entropy state signing secret; generate with `secrets.token_urlsafe(48)` |
| `ACCOUNTS_OIDC_ISSUER` | Exact HTTPS issuer matching verified ID-token claims |
| `ACCOUNTS_OIDC_CLIENT_ID` | Registered confidential web-client ID |
| `ACCOUNTS_OIDC_CLIENT_SECRET` | Server-only identity-provider client secret |

Register the callback as `ACCOUNTS_ORIGIN + /auth/callback`. Register allowed logout/application URLs with the provider as appropriate. Local logout revokes this app's session; it does not terminate the provider's global SSO session. Use a controlled TLS ingress, preserve the configured Host, and trust forwarded scheme/IP headers only from that ingress. Do not enable unrestricted forwarded-header trust or bind the existing unauthenticated local backend publicly.

Real market-provider keys are not needed to test this phase. External data-display licensing, account privacy/export/deletion policy, hosted encrypted storage, operational monitoring, restore drills and a production identity login remain release gates. No hosting subscription, identity account, public endpoint or paid provider plan was created.

## Verification

The complete offline suite passes with 417 Python tests and 90 frontend tests. New cases cover account isolation, owner-field rejection, session rotation/expiry/logout, CSRF/Host/Origin restrictions, local-only sample mode, malicious input, request limits, concurrent edits/imports, cancel/expiry/replay/stale revision checks, unsigned identity rejection and OIDC signature/issuer/audience/nonce/state/expiry/verified-email checks. Async HTTP provider calls are blocked unless a mock or in-process transport is explicitly injected. Dependency checks report no conflicts.

Browser checks used only synthetic sample accounts and a synthetic import file: Avery saved a watchlist/holding/rule; Sam initially saw an empty workspace; Sam previewed and confirmed the sample import; Avery's workspace remained unchanged. The file itself and existing user portfolios were not modified. Responsive and browser-console checks are recorded with the staging preview.

Implementation references: [Authlib's Starlette OIDC integration](https://docs.authlib.org/en/latest/client/starlette.html), [Starlette session middleware](https://www.starlette.io/middleware/). Security controls are tested in-process; they are not a substitute for deployment and independent security acceptance.
