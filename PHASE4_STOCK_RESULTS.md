# Initial stock/ETF baseline results — 2026-10-12

Exploratory retrospective five-session direction models, not production predictions. The protocol was saved before fitting. Three catalog-resolved surviving assets were selected; no test-based tuning or promotion was performed.

| Asset | Daily observations | Eligible test targets | Logistic accuracy | Always-up accuracy | Balanced accuracy | Descriptive accuracy interval |
|---|---:|---:|---:|---:|---:|---|
| AAPL | 2512 | 371 | 55.3% | 57.4% | 48.9% | 46.1%–64.4% |
| IBM | 2512 | 371 | 53.9% | 53.1% | 53.6% | 46.4%–61.2% |
| SPY | 2512 | 371 | 62.0% | 62.0% | 50.0% | 53.9%–70.1% |

Apple underperformed always-up. IBM exceeded it by less than one percentage point, which does not establish a reliable advantage. SPY tied always-up. Accuracy intervals are descriptive moving-block bootstrap intervals, not proof of independent observations or superiority.

Each request returned 2,512 sessions over nearly ten years, through 2026-10-09. The just-completed 2026-10-12 session was unavailable; its absence is preserved, not filled. Feature/label construction excludes unavailable targets. Latest-session live indicator acceptance remains incomplete.

Prices are split-adjusted and exclude dividends. Current provider history is revised, with no corporate-action vintage archive or guaranteed delisted coverage. Targets overlap. The reports also contain probability scores, confusion counts, validation outcomes and cost scenarios. No displayed accuracy badge, calibrated probability, stock AI recommendation or automatic trading was added. None of these models is promoted.

## AAPL
Observed 2016-10-12 through 2026-10-09. Missing requested sessions: 2026-10-12.
Purged splits: {'train': 1726, 'validation': 366, 'test': 371}. Test dates: 2025-04-11 through 2026-10-02.
Source ID: `fff5951199ea73b606b382a92e7ef0bae3de0f4ea192c2953df6daef4ab86386`. Feature ID: `a6df94f585fd5dbf8366c38ffe1738a2702b38063b3e2b73bc3c8b733f7a0928`.
Report: [immutable JSON](model_reports/2900688b7f4819749657c77490272622331ed174bb6880fe0ee6cf2a43d3f246.json). Offline reproduction matched exactly.
Illustrative execution (compounded return at 0/10/25 bps round-trip costs, not total return): `{"always_up": {"trades": 62, "returns": {"0": 1.0457186153842706, "10": 0.9239641177173794, "25": 0.7545832863190387}}, "logistic": {"trades": 60, "returns": {"0": 0.40181678109584307, "10": 0.32052575959600005, "25": 0.20720698113445013}}}`.

## IBM
Observed 2016-10-12 through 2026-10-09. Missing requested sessions: 2026-10-12.
Purged splits: {'train': 1726, 'validation': 366, 'test': 371}. Test dates: 2025-04-11 through 2026-10-02.
Source ID: `09a5f12954a972641c3538ffa44d53187ac2ff25768d40c615558d53039e56e1`. Feature ID: `e9d3a7abae07717a7109e3b3e09401ebeaab7e8f0e30f8979cff99ee3e85efa7`.
Report: [immutable JSON](model_reports/e4d9b7a63d8acff9cdaa7f23e50e1d03d674b8cdb0f601704d7e6b803a9e08bf.json). Offline reproduction matched exactly.
Illustrative execution (compounded return at 0/10/25 bps round-trip costs, not total return): `{"always_up": {"trades": 62, "returns": {"0": 0.1487920288673188, "10": 0.07976050965561243, "25": -0.016202213111233044}}, "logistic": {"trades": 42, "returns": {"0": 0.8646881427124442, "10": 0.7890007076806369, "25": 0.6810614119707892}}}`.

## SPY
Observed 2016-10-12 through 2026-10-09. Missing requested sessions: 2026-10-12.
Purged splits: {'train': 1726, 'validation': 366, 'test': 371}. Test dates: 2025-04-11 through 2026-10-02.
Source ID: `7dbba9d0480c3f49c437ad99788cfb1dc037aeacc538bc1109a79e144c51b9a9`. Feature ID: `cd8cf5cdbae5440fc1facc75a1e4b9427eb3bc99a065f9c7f64a0818bd04aeea`.
Report: [immutable JSON](model_reports/9ffbb9fb6df0356af55f7e668dec47d043e2263a1c72b95c10b0573c137c8caa.json). Offline reproduction matched exactly.
Illustrative execution (compounded return at 0/10/25 bps round-trip costs, not total return): `{"always_up": {"trades": 62, "returns": {"0": 0.3502046775433181, "10": 0.26936416774886585, "25": 0.15695383265872187}}, "logistic": {"trades": 62, "returns": {"0": 0.3502046775433181, "10": 0.26936416774886585, "25": 0.15695383265872187}}}`.
