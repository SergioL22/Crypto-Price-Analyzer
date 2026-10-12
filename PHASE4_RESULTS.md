# Phase 4 baseline experiment — 2026-10-06

The offline baseline experiment is complete. Neither model qualifies for user-facing recommendations. No model was tuned after seeing these results.

## What operates now

`modeling.py` loads a saved feature artifact and verifies its parent snapshot, splits chronologically, purges overlapping boundary labels, learns scaling from training data, and fits a fixed regularized logistic regression. A small NumPy Newton solver uses line search and rejects non-convergence. Tests verify the fitted objective's gradient. No additional dependency installation, provider request, API key, or LLM call is needed.

Each asset has 222 training rows, 44 validation rows and 49 test rows. Test signal dates are August 12–September 29, 2026; five-day target outcomes extend through October 4. Validation is reported but does not select parameters or trigger a refit. The earlier dataset audit had inspected aggregate outcome counts; this is retrospective research.

## Held-out results

| Measure | Bitcoin | Ethereum |
|---|---:|---:|
| Logistic direction accuracy | 34.7% (17/49) | 34.7% (17/49) |
| Always-up accuracy | 57.1% | 59.2% |
| Training-prior accuracy | 42.9% | 40.8% |
| Momentum accuracy | 32.7% | 42.9% |
| Logistic balanced accuracy | 39.9% | 42.5% |
| Logistic Brier score (lower is better) | 0.2878 | 0.3696 |
| Training-prior Brier score | 0.2606 | 0.2780 |
| Descriptive block-bootstrap accuracy interval | 12.2–61.2% | 22.4–49.0% |

Always-up and momentum emit hard zero/one probabilities, so their probability losses penalize their artificial certainty; use the training-prior baseline for the useful probability comparison. The logistic models underperformed that baseline too. Their output probabilities are not calibrated confidence percentages.

The 49 labels overlap, Bitcoin and Ethereum are correlated, and the archive covers only one year. Bootstrap intervals are descriptive estimates under block-resampling assumptions, not guarantees or independent sample counts. There is no evidence here of reliable predictive advantage.

## Illustrative execution

Signals enter at the next daily sample and exit five sessions later. A later entry must be after the previous exit; missing observations prevent execution. This differs from the current-sample-to-five-days-later classification target. Daily samples are not promised tradable prices.

At 10 basis points total round-trip costs, the model took one trade per asset: Bitcoin −1.19%, Ethereum −1.69%. The repeated-long comparator took eight trades and returned +30.11% and +39.03% respectively. This comparator follows the same timing rules, but its accepted signal dates differ from the model's and it has gaps between positions; it is not continuous buy-and-hold. Reports also retain 0 and 25 basis point scenarios. These tiny trade counts do not validate a strategy. Cash earns zero interest; tax, market impact and actual execution are not modeled.

## Reproduce

From the project directory using its Python environment:

```powershell
.\.venv\Scripts\python.exe modeling.py 52086787adefb9bfe2578ed1050ceb98e8a2ee46b57e7372a39f289e915f9943
.\.venv\Scripts\python.exe modeling.py a2a5d1ad2567dd8a0a0f5fa552b28298a27e54dcf122d1664b68db1a445e1325
```

Requires the local `research_datasets.db`. Output defaults to `model_reports/`; `--store` and `--output` accept alternate paths. Reports include all predictions, labels, split dates, model coefficients/scaling, source hashes, protocol/code hashes, Python/NumPy versions and execution details. Same inputs/code/environment reproduce the same report; changed versions may change numerical results and report IDs. JSON reports contain public research values and no secrets or portfolio holdings.

Saved reports:
- Bitcoin: `model_reports/3498a598f3a61bb825d2c5d59bd230e524f9f6dc630818e5eb0b6919a6caa449.json`
- Ethereum: `model_reports/25aa90458c8a462296d127582ef5ca7d0024dc0845ca91eb05d861486711bd67.json`

## Verification and next steps

373 Python tests passed with strict markers/configuration and live requests blocked. Seven new tests cover split purging, future-data isolation, deterministic output, optimizer stationarity, inadequate history/single-class rejection, known metrics, delayed/nonoverlapping execution and costs, missing data and parent integrity. Two existing dependency deprecation warnings remain. Dashboard files were unchanged.

This completes the initial crypto baseline scope of Phase 4, not production prediction readiness. No stock/ETF model, walk-forward multi-regime evaluation, calibrated probability, promoted model or app prediction button was added. Longer properly licensed histories, fresh untouched evaluation periods and prospective paper predictions remain necessary for stronger claims. The scheduled UI polish can proceed now; research improvements must use a new recorded protocol rather than repeatedly optimizing against this exposed test period. Changes remain local, uncommitted and unpushed.
