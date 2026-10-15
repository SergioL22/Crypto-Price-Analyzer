# Prospective validation reporting — fixed October 14, 2026

This extends reporting, not the fitted model or issuance protocol. The ten October 13 predictions exist, but no completed outcomes have been seen when this reporting design is written. Existing historical evaluation results remain exploratory; they are not newly blind evidence.

## Target and comparisons

Use only verified append-only predictions with their subsequently settled outcomes. Target: five completed exchange-session close-to-close direction, excluding dividends, execution costs and profit claims. Score model, always-up, training-prior and five-session momentum on exactly the same completed outcomes, at a fixed 0.5 decision threshold. Report direction accuracy, balanced accuracy when both classes exist, Brier score, log loss and confusion counts. Never infer accuracy from the model's probability or LLM confidence.

Group by the exact issuance protocol and implementation hashes. Do not pool incompatible cohorts. Show asset and calendar-quarter results and their counts; a quarter is a time grouping, not a proven market regime. Pooled metrics weight completed observations, so an asset with more outcomes can dominate them. Users must inspect breakdowns rather than cherry-picking favorable assets or periods.

## Dependence and uncertainty

Parallel asset outcomes from a shared target period are correlated. Sort unique target windows and greedily retain the earliest window whose start is after the previous retained end, without consulting outcomes. This yields a descriptive count of nonoverlapping start dates, not a count of independent market regimes.

For paired model-minus-baseline Brier differences, average asset losses within each retained date, giving dates equal weight. With at least 20 such dates, report an exploratory date-cluster percentile bootstrap interval (2,000 replicates, seed 42). Below that threshold, report no interval. Twenty dates is a reporting cutoff, not proof of adequate sample size. Nonoverlapping dates may still be serially dependent, and selected assets may share risks; these intervals do not establish a definitive advantage or promotion gate.

Use five fixed probability bins [0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1], including probability 1 in the last bin. Show count, mean probability and observed up frequency. These are calibration diagnostics, not a fitted calibration model or calibrated probability claim.

## Promotion and collection

Reporting never promotes a model: `promoted=false`, `calibrated=false`, and no validated accuracy badge. Sufficient future coverage, performance versus all baselines, asset/regime stability, dependence-aware uncertainty and separate calibration/review remain necessary. No promised accuracy level, newly tuned parameters, backdated forecasts or automatic trading are introduced.

The existing follow-up handles the current ten-prediction batch after its final target session closes. It does not establish ongoing issuance or an unattended long-term data pipeline. Future batches must retain the same issuance, freshness and settlement validation gates. Local journal/data files must be preserved for reproducibility.
