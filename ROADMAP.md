# Product roadmap

## Phase 1 — local research dashboard

Implemented locally:
- Cached CoinGecko catalog, searchable dropdown, quick choices and manual ID fallback.
- Same-snapshot historical chart with optional moving averages and Bollinger Bands.
- Plain-language trend, RSI, MACD, Bollinger and support/resistance explanations.
- Explicit missing-history, stale-data and unavailable-AI states.
- Exact evidence and limitations available in expandable details.
- Browser-local watchlist of up to 50 coin IDs, with explicit add/remove and no automatic provider requests.
- Offline Python and JavaScript regression tests; dashboard CI jobs configured for Windows and Linux.

Next milestones:
1. Review the complete beginner flow at phone and desktop widths, including catalog failures and empty selections.
2. Verify saved watchlist persistence and storage-failure recovery in the normal user browser; account/device synchronization is deferred.
3. Define dashboard portfolio behavior, including cost basis, cash flows, valuation freshness and import/export.
4. Bring existing price/RSI alerts into the dashboard; define scheduling, duplicate suppression and alert history before extending to crossover alerts.

Phase 1 is complete when these user flows have been implemented, tested offline and verified in the browser. Local implementation and hosted CI success are separate milestones; new workflow jobs must pass after publishing.

## Later phases

2. Shared asset identity and stock/ETF data adapters: provider coverage, exchange and currency identity, corporate actions, delisted assets and data licensing.
3. Versioned historical datasets and point-in-time features, including market context and trading calendars.
4. Baseline prediction models with predefined targets and horizons, chronological validation, leakage checks and a held-out evaluation period. Compare prediction quality to simple baselines and strategy outcomes after costs.
5. Prediction-aware recommendations: keep numeric predictions, calibrated probabilities, measured historical performance and language-model explanations distinct. Allow no recommendation when evidence is insufficient.
6. Model registry, prediction journal and monitoring: immutable evidence/model snapshots, later outcomes, sample sizes, uncertainty, recent and long-term performance, calibration and performance across market conditions. Paper trading precedes any real trading integration.
7. Authentication, private accounts, background work, cost controls and a mobile client on the shared backend. Public deployment requires a separate readiness review.

No target accuracy is promised. Per-asset performance percentages require sufficient out-of-sample observations and a clearly stated horizon, period and uncertainty. Model confidence must not be presented as historical accuracy. The language model explains validated numeric outputs and cannot silently replace them.
