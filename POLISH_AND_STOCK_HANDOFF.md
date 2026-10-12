# Polish and stock baseline handoff — 2026-10-12

## UI

Stocks & ETFs remains home, with Crypto as the second market. Each market exposes only its own saved-item workspace. Stock selection places the company/fund and time range side by side on desktop and stacks them on phones. Provider catalogs still load explicitly; no new automatic requests or retries were added. Crypto manual IDs remain available under a disclosure. Saved watchlists, holding snapshots and alert rules use readable cards and actionable empty states. Storage and history notes are expandable.

Latest historical prices use a large bold value; small nonzero prices retain significant digits. Charts start with one price line. Moving averages, bands, observation inspection and exact tables remain available in Chart tools. Coverage diagnostics, detailed indicators and crypto strategy context are expandable; missing-data warnings remain visible. Prices are historical closes/samples, not live quotes. Existing saved data formats and stores are unchanged.

## Dataset and modeling

`dataset_cli.py capture stock|etf <catalog-asset-id> --days 3653` now supports decade requests. Crypto still allows only 35–364 days. Normalized snapshots, expected sessions, gaps, adjustment metadata and feature artifacts remain immutable in the separate ignored research SQLite store.

The initial stock experiment selected Apple, IBM and SPY before fitting, used a fixed five-session direction target and eight causal features, and retained purged chronological splits. The full stock-specific protocol is PHASE4_STOCK_PROTOCOL.md. Live captures yielded 2512 sessions each, through October 9; October 12 was unavailable. No missing price was filled.

Logistic test accuracy was 55.3% for Apple, 53.9% for IBM and 62.0% for SPY on 371 overlapping targets each. Always-up scored 57.4%, 53.1% and 62.0%, respectively. These numbers do not establish useful predictive superiority. No model was promoted, and no recommendation/accuracy badge was enabled. PHASE4_STOCK_RESULTS.md links each content-addressed report and records uncertainty, splits, input IDs and illustrative cost results. All three reports reproduced exactly from saved inputs, with protocol hashes verified.

## Verification and release

381 Python tests passed with the offline provider guard and strict pytest configuration. 76 JavaScript tests passed, including unique page IDs/scripts, route scoping, price formatting and collapsed chart inspection. The existing two test dependency deprecation warnings remain. `git diff --check` passed.

Browser verification used an isolated sample-provider server at port 8001, leaving the user's app and data untouched. Desktop stock selection/results and phone-width stock results, crypto selection, both markets' Watchlist/Portfolio/Alerts/Settings, and comparison were checked. No page overflow occurred; filter Escape dismissal and collapsed chart tools were verified. These checks do not claim live acceptance of every endpoint or production/mobile readiness.

The accumulated repository changes are local and uncommitted. No staging, commit or push was performed. Existing unrelated changes were preserved. A commit review should include the complete multi-phase diff, new source/tests/docs and model reports while excluding `.env`, runtime databases/logs and local tooling settings. Hosted CI remains to be run after publication.

Next modeling work: broader predeclared asset/regime evaluation, stronger simple baselines, fresh prospective outcomes and calibration. Avoid selecting the next model based only on these held-out results.
