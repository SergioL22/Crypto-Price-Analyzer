# Expanded dataset audit — 2026-10-12

Live capture UTC: 2026-10-13T01:23:12.934294+00:00

All ten predefined assets were captured live from catalog-resolved listings; no cached fallback or substitution was used. No model was fitted.

| Symbol | Exact listing | Observations | Usable five-session targets | Missing sessions |
|---|---|---:|---:|---|
| MSFT | twelvedata:stock:XNGS:USD:MSFT | 2512 | 2473 | 2026-10-12 |
| JNJ | twelvedata:stock:XNYS:USD:JNJ | 2512 | 2473 | 2026-10-12 |
| JPM | twelvedata:stock:XNYS:USD:JPM | 2512 | 2473 | 2026-10-12 |
| XOM | twelvedata:stock:XNYS:USD:XOM | 2512 | 2473 | 2026-10-12 |
| QQQ | twelvedata:etf:XNMS:USD:QQQ | 2512 | 2473 | 2026-10-12 |
| IWM | twelvedata:etf:ARCX:USD:IWM | 2512 | 2473 | 2026-10-12 |
| DIA | twelvedata:etf:ARCX:USD:DIA | 2512 | 2473 | 2026-10-12 |
| AAPL | twelvedata:stock:XNGS:USD:AAPL | 2512 | 2473 | 2026-10-12 |
| IBM | twelvedata:stock:XNYS:USD:IBM | 2512 | 2473 | 2026-10-12 |
| SPY | twelvedata:etf:ARCX:USD:SPY | 2512 | 2473 | 2026-10-12 |

Observed window for every asset: 2016-10-12 through 2026-10-09. Each requested window contains 2,513 expected completed sessions; the October 12 bar was not returned. Its cause is not established by this audit. The date remains missing, not filled. These snapshots must not be used as fresh October 12 prediction inputs.

## Yearly sample counts

| Year | Purged training rows | Completed test targets | Block |
|---|---:|---:|---|
| 2021 | 1024 | 247 | Full year |
| 2022 | 1276 | 246 | Full year |
| 2023 | 1527 | 245 | Full year |
| 2024 | 1777 | 247 | Full year |
| 2025 | 2029 | 245 | Full year |
| 2026 | 2279 | 189 | Partial |

Counts are identical across these ten assets. All blocks meet the predefined computational eligibility thresholds. This is data coverage, not measured model performance. Test labels ending after the calendar block are excluded. Training labels ending on or after the first eligible test feature date are purged.

## Frozen inputs

Each SHA-256 references an immutable, integrity-checked artifact in the local ignored research database. Preserve that database to reproduce the experiment.

### MSFT

Snapshot: `634c72103efb384f123128325647e75fe7c0eb0f2c6b965f6d766badbf12d72a`

Features: `79ef8a32ee64dc03d70d9dbd7368efea03769ecd0db47d943f106a6bd4fe1d34`

### JNJ

Snapshot: `f1db47fb7a37bb8be08be00f183d871efd94ffa62bcbb4dd6804bea736eb4519`

Features: `eba7e39c3a49cb5fadf623371519e94959cfa5976e553d13727a4506f88de089`

### JPM

Snapshot: `716ea6849c262a02b03f0b724655ad4e24b5517c7f62906b1038f903e690d0f9`

Features: `55330736306046d00fd72da19f116f7ebc728007bc2385923c50aa66d3f991ad`

### XOM

Snapshot: `dfecc06a19cfa17de2b8eea461c91a8c84b2a7bea1ad25c9299cd8f61b0b963c`

Features: `99a613a26249acfc25c20d2dedb97a820c6e79103920307b35a3126ed36ddae1`

### QQQ

Snapshot: `c22fe70493acf3f91846ee9d728aeac09737b3b4a5f70af94779b7880cef31ea`

Features: `52700f40f12213f28af69d9168e5b775795b677aec478f64819c639bca1a2544`

### IWM

Snapshot: `741ec670b6a6ced24fbb15470a7a6ebfe7d853591e29fb8d0c240820909e4bb8`

Features: `3862fd1aa522a64f5fb367e38298293fc104d11f0bc6c6cf2804e88bd8508926`

### DIA

Snapshot: `e8b1afc46bf668809a44d79ebf61a615a6cb8b9a53effa4e2c22242c095c2013`

Features: `ab65d2f3e54857e599091b1c37b976a40e29964a99f8b24d86894022bf694070`

### AAPL

Snapshot: `9df19a43c9adb0c4ce35c8767bde6a31bd908ef36f4e9a3e156fec5c5cc82329`

Features: `b7cd056e08ca221367bdbd4edc1b683b393910eebfd36f777c2890cc39fcd25e`

### IBM

Snapshot: `8040a62e07258e61f85687ec94148e66f7d5d55d4f37c719b5b504d2d798cdd4`

Features: `059bb849aa50612433a5749ada56c4dd39070f54526108be6d80f0fd35976626`

### SPY

Snapshot: `4d57768b5379656ba09690bac36a1e9b898d11e186217b2c086e26657e2b70b7`

Features: `d9d1a97b4073cb14f9941a0bda977b8b6b07e17da25baaa69e348192fa2e158d`

## Limits and next step

The universe is deliberately selected from current listings, excludes delisted coverage and dividend-inclusive returns, and uses present-day provider adjustments rather than historical vintages. AAPL, IBM and SPY remain previously studied controls. The next experiment is exploratory yearly evaluation against all predefined baselines; no accuracy, calibration or promotion claim follows from this audit.

Validation: 386 offline Python tests and 84 frontend tests passed. Five new Python tests cover identity ambiguity, missing snapshots, quota stopping, stale catalogs and chronological target purging.
