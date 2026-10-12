# Initial dataset audit — 2026-10-05

Scope: Bitcoin and Ethereum only, per user direction. No Twelve Data or OpenAI calls were made. Live CoinGecko daily history was captured into the separate ignored research_datasets.db. Runtime holdings and alerts were not read or modified.

## Coverage and usable rows

| Asset | Requested dates (UTC) | Observations | Missing days | Five-day supervised rows |
|---|---|---:|---:|---:|
| Bitcoin | 2025-10-06 – 2026-10-04 | 364 | 0 | 325 |
| Ethereum | 2025-10-06 – 2026-10-04 | 364 | 0 | 325 |

October 5 was excluded as the unfinished UTC date at capture. Indicator warm-up excludes the first 34 observations, and a five-observation target excludes the final five rows from supervised use. Prices passed snapshot validation. These are provider daily samples, not guaranteed exchange closing prices; no independent provider price reconciliation was performed.

Both feature artifacts rebuilt to exactly the same content IDs. A 150-observation prefix produced exactly the same feature values as the corresponding prefix of the full capture. Integrity hashes were checked on load. An additional Ethereum artifact uses Bitcoin as the benchmark; all 325 supervised rows remain eligible.

## Phase 4 readiness

Ready for exploratory baseline experiments, not production performance claims. A provisional chronological 70/15/15 allocation, excluding training/validation labels that reach the following block, gives 222 training rows, 44 validation rows and 49 final test rows per asset. Validation starts 2026-06-24; the final block starts 2026-08-12. These are planning counts, not a fitted model or a scored evaluation. Freeze the actual evaluation protocol before training.

Five-day labels on adjacent dates overlap, so these rows are not independent observations. The assets also share market conditions; pooling them does not create independent years of evidence. One year omits many market regimes. Do not promise an accuracy percentage or use repeated test-set tuning. Baseline comparison, train-only scaling, chronological validation, label-boundary purging, costs/execution assumptions and dependence-aware uncertainty remain Phase 4 work.

This capture does not resolve revised-history, delisted coverage, historical universe selection, dividend/corporate-action or historical publication-time limitations. Stock/ETF datasets are intentionally deferred for now. No model was trained or scored during this audit.

## Artifact identities

### bitcoin

- Snapshot: `ff6375d370fc67545a2b550d1344d0ac767ce0dc72b934a2d68387a4479e874a`
- Features: `52086787adefb9bfe2578ed1050ceb98e8a2ee46b57e7372a39f289e915f9943`
- Captured UTC: `2026-10-05T17:38:25.211188+00:00`

### ethereum

- Snapshot: `106ab7ae00395008c9fbbb7d16cd4b79a587484b00be26c8a4d97a60e80e2e97`
- Features: `a2a5d1ad2567dd8a0a0f5fa552b28298a27e54dcf122d1664b68db1a445e1325`
- Captured UTC: `2026-10-05T17:38:25.832549+00:00`
- Features with Bitcoin benchmark: `bb04160fa75131233aeb7ef472e6aa3e6ade3c614b1bd8ecafea479f65b992d7`
