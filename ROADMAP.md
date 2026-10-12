# Product roadmap

## Polish and stock experiments update — 2026-10-12

Completed locally: navy/blue two-market navigation, compact stock asset/time selection, manual crypto IDs behind a disclosure, bold price summaries, price-only charts with expandable tools and exact values, market-scoped saved-item cards and empty states, and expandable storage/coverage notes. Duplicate home-page scripts/IDs were removed and covered by regressions. Phone-width browser checks covered stock analysis, all saved-item pages in both markets, crypto selection and comparison; no horizontal page overflow.

Phase 3 captures now accept up to 3660 days for stocks/ETFs while retaining the 364-day crypto limit. The predefined Phase 4 stock protocol captured Apple, IBM and SPY with 2512 observations each. The latest requested session (2026-10-12) was missing and is preserved as a gap. Three fixed baseline evaluations were archived and reproduced exactly offline. None is promoted: Apple underperformed always-up, IBM exceeded it only slightly, and SPY tied it. See PHASE4_STOCK_PROTOCOL.md and PHASE4_STOCK_RESULTS.md. Production validation, calibration, historical vintages and delisted coverage remain open.

Verification: 381 Python tests and 76 JavaScript tests passed; whitespace check passed. Changes remain local and uncommitted. Hosted CI and publication are release tasks, not completed checks.

## Stocks-first priority update — 2026-10-07

Before further prediction phases, the home page now prioritizes Stocks & ETFs, with crypto on a separate page. Implemented locally: decade-history requests and presets, stock/ETF name/class/exchange filters, a free explicit five-listing YTD/volume/price comparison, browser-local stock watchlists/holding snapshots/manual close-or-RSI alerts, and stock workspace backup/restore. User preference is free operation now with a future paid screening adapter behind stable ranking fields. Whole-market rankings, fundamentals filters, unified server-saved portfolios, longer research-dataset captures and live decade-data acceptance remain open. See STOCKS_FIRST.md for exact operation, storage boundaries, tests and upgrade plan.

## Phase 1 — local research dashboard (complete locally, 2026-09-27)

Implemented locally:
- Cached CoinGecko catalog, searchable dropdown, quick choices and manual ID fallback.
- Same-snapshot historical chart with optional moving averages and Bollinger Bands.
- Plain-language trend, RSI, MACD, Bollinger and support/resistance explanations.
- Explicit missing-history, stale-data and unavailable-AI states.
- Exact evidence and limitations available in expandable details.
- Browser-local watchlist of up to 50 coin IDs, with explicit add/remove and no automatic provider requests.
- Read-only saved portfolio with price freshness, partial valuations, unrealized gain/loss and allocation bars; explicit loading, no AI calls.
- Dashboard holding editor sets total quantity and average purchase price, with atomic saves and stale-version rejection. Snapshot editing is separate from recording trades; transaction history, cash-flow accounting and realized P&L are deferred.
- Holding removal shows saved values for confirmation, preserves other entries and rejects stale requests.
- Explicit JSON portfolio backup download preserves saved quantities, purchase prices and metadata without provider calls or file changes. Restore previews full replacement, validates the saved version and preserves a recovery copy before applying it.
- Manual price/RSI alerts with create, pause/resume, confirmed removal, freshness checks, persistent duplicate suppression and trigger history. Background scheduling and push notifications remain later-phase work.
- Section navigation, market results directly under controls, and responsive forms for desktop and phone-sized layouts.
- Offline Python and JavaScript regression tests; dashboard CI jobs configured for Windows and Linux.

Completion evidence:
1. Offline regression suite: 314 Python tests and 43 JavaScript dashboard tests passing. Python strict markers/configuration checks enabled; provider calls blocked by the test fixture.
2. Browser checks with isolated sample data: chart and explanations, catalog-failure fallback, watchlist persistence after reload, AI-unavailable evidence, restore preview, alert trigger/history and duplicate suppression. Desktop and 390px phone layout checked; no horizontal page overflow. Storage-denial and invalid-state recovery are covered by simulated browser tests.
3. Project virtual environment: backend startup and dependency compatibility pass. Test execution used the installed system Python because the runtime virtual environment has no pytest.
4. Portfolio editing is explicitly a holding snapshot. Transaction history, cash flows, realized returns, account/device synchronization and background/push alerts are deferred; none are implied by this completion.

Release status: implementation is local and uncommitted. Commit/push and a fresh hosted CI run remain release tasks, not completed checks. See PHASE1_COMPLETION.md for the handoff and verification limits.

## Phase 2 — US stock/ETF research (implemented locally; live acceptance pending)

Shared provider-qualified asset identities, a Twelve Data adapter, cached US stock/ETF discovery, completed-session charts and indicators, typed API endpoints, and explicit adjustment/coverage limitations are implemented. Live Apple, IBM and SPY requests succeeded; those windows lacked the latest expected session and correctly withheld indicators. Complete-window live acceptance and intended display rights still need verification. Corporate-action archives, historical identifier resolution and guaranteed delisted coverage remain open data-acquisition work for Phase 3; do not treat the catalog as a point-in-time training universe. See PHASE2_COMPLETION.md for operation and scope.

## Phase 3 — reproducible dataset pipeline (implemented locally, 2026-10-05)

Content-addressed normalized snapshots in a separate SQLite store; explicit coverage/adjustment/provenance; causal gap-aware daily features; optional same-calendar benchmark context; separate forward-return labels; offline reproducible derivation and integrity checks. See PHASE3_DATASETS.md. An initial live crypto-only capture is saved: Bitcoin and Ethereum each have 364 complete daily observations and 325 usable five-day-target rows. Reproducibility and prefix invariance checks passed. See INITIAL_DATASET_AUDIT.md; one year supports exploratory baselines, not strong accuracy claims. Historical vintages, corporate-action archives, delisted coverage and long-history entitlements remain data-acquisition limitations, not solved by storage.

Phase 4 initial crypto baseline experiment is complete locally (2026-10-06): fixed five-day logistic models, purged chronological validation/test periods, simple baselines, reproducible predictions and illustrative costs. Both models scored 34.7% on 49 overlapping test outcomes and underperformed the always-up and training-prior baselines. Neither is promoted to recommendations. See PHASE4_PROTOCOL.md and PHASE4_RESULTS.md. Production prediction validation, longer histories and stock/ETF experiments remain open. Next is the requested UI polish pass. Correctness fixes and testing continue throughout.

## Later phases

4. Baseline prediction models with predefined targets and horizons, chronological validation, leakage checks and a held-out evaluation period. Compare prediction quality to simple baselines and strategy outcomes after costs.
5. Prediction-aware recommendations: keep numeric predictions, calibrated probabilities, measured historical performance and language-model explanations distinct. Allow no recommendation when evidence is insufficient.
6. Model registry, prediction journal and monitoring: immutable evidence/model snapshots, later outcomes, sample sizes, uncertainty, recent and long-term performance, calibration and performance across market conditions. Paper trading precedes any real trading integration.
7. Authentication, private accounts, background work, cost controls and a mobile client on the shared backend. Public deployment requires a separate readiness review.

No target accuracy is promised. Per-asset performance percentages require sufficient out-of-sample observations and a clearly stated horizon, period and uncertainty. Model confidence must not be presented as historical accuracy. The language model explains validated numeric outputs and cannot silently replace them.
