# Phase 4 protocol v1

Fixed before model fitting or held-out scoring, 2026-10-06. Earlier dataset quality checks inspected aggregate label counts; this is an exploratory retrospective experiment, not a prospective trial.

- Bitcoin and Ethereum separately; stored daily-v1 eight-feature artifacts, five-session up/down target. The optional benchmark variant is excluded from this first experiment.
- Chronological 70/15/15 split by eligible row count. Purge any training/validation target ending on or after the next block's first feature date. Require at least 100/20/20 remaining rows and both training classes.
- Standardize using training means/population standard deviations only. Fit logistic regression with fixed L2 penalty 1 on coefficients, unpenalized intercept, summed negative log likelihood, deterministic Newton optimization. No hyperparameter selection, refit, probability calibration or test-based tuning. Classification threshold 0.5.
- Compare always-up, training positive-rate and five-day momentum baselines on the same rows. Report accuracy, balanced accuracy, Brier score, clipped log loss and confusion counts for validation and test. Model probabilities are uncalibrated.
- Descriptive 95% accuracy intervals: circular moving-block bootstrap, block length 10, 2,000 resamples, seed 42. These do not establish independent observations or eliminate selection/regime uncertainty.
- Illustrative long/cash simulation: test signals only, enter at the next stored daily sample, exit five sessions later, one position at a time, no same-sample re-entry. Missing sessions invalidate a trade. No shorts. Compare always invested under the same entry schedule. Fixed total round-trip costs of 0, 10 and 25 basis points, subtracted from each trade return before compounding. Daily samples are not guaranteed executable prices; this timing differs from the prediction target. Report returns and counts, not an executable strategy or portfolio-equity drawdown.
- Save input IDs, protocol and implementation hashes, environment versions, model parameters, split membership, probabilities, outcomes and trades to a content-addressed JSON report. No pickle, live data, LLM requests or dashboard accuracy badge.

Only one year of revised provider history and 49 overlapping test targets per asset are available. This completes a reproducible baseline experiment, not production model validation. New model selection requires a newly defined experiment and eventually fresh unseen data.
