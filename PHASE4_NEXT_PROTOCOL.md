# Next Phase 4 experiment plan — 2026-10-12

This plan is fixed before additional fitting. No new models have been fitted under it. The existing Apple/IBM/SPY retrospective results are known and cannot become a fresh blind test by relabeling them.

## Scope

Expand the explicit catalog-resolved research universe to MSFT, JNJ, JPM, XOM, QQQ, IWM and DIA, with AAPL, IBM and SPY retained as previously evaluated controls. Request up to 3653 days; record missing dates, entitlements and exact listing identities. Do not silently substitute assets after looking at results. This deliberately selected current universe has survivorship and selection bias and does not represent all stocks.

## Evaluation design

Keep the eight daily-v1 causal features, five-session direction target, training-only scaling, fixed L2=1 logistic regression and 0.5 threshold. Add an expanding-window evaluation with calendar-year test blocks for 2021 through 2025 and a separately labeled partial 2026 block. For each block, train only on earlier eligible rows, purging any target ending on or after the block's first feature date. Require at least 500 training rows and 100 completed test targets per full-year block; otherwise mark that block unavailable. Do not refit within a test block, optimize thresholds or select hyperparameters from test outcomes.

Compare always-up, training-prior and five-session momentum on identical eligible rows. Report accuracy, balanced accuracy, Brier score, log loss, confusion counts, class balance, block-bootstrap uncertainty, and illustrative long/cash outcomes under the existing 0/10/25 bps scenarios. Report each asset/year and an equal-weight asset summary; do not pick only favorable assets or years. Dividends remain excluded, so do not call these total returns.

These historical blocks provide exploratory regime checks, not untouched prospective evidence. They may have been studied indirectly during prior development. No model is promoted solely from this experiment.

## Fresh outcome journal

After the expanded evaluation, implement an append-only manual prediction journal. Each entry must be saved before its target window completes and include UTC issuance time, exact model/input/feature hashes, last available completed session, five-session target horizon and probability. Reject stale/incomplete inputs rather than backdating a prediction. Outcomes are attached later without rewriting the original prediction. No retrospective forecasts count as prospective results.

New journal observations begin only when the journal is actually implemented and a prediction is issued; October 13 is not an automatic or assumed start date. Do not create a schedule or background collector as part of this plan. Predictions remain research-only and probabilities uncalibrated.

## Promotion gate

Require sufficient fresh completed outcomes, performance against all predefined baselines, calibration assessment, stability across assets/regimes and uncertainty analysis before considering a recommendation integration. A numeric accuracy percentage must state the target, period, sample size and limitations. No promised target accuracy or trading integration.
