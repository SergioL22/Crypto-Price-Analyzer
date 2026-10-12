# Phase 4 stock/ETF exploratory protocol

Defined before fitting or scoring this experiment, 2026-10-12.

Universe: Apple (AAPL), IBM (IBM), and SPDR S&P 500 ETF (SPY), resolved to explicit provider catalog identities. Request 3653 calendar days of regular-session split-adjusted prices. Save original normalized snapshots and coverage, without filling gaps or claiming point-in-time history. Current catalog selection has survivorship bias. Dividends are excluded; ETF returns are not total returns.

Use the same eight causal daily features, five-session up/down target, purged chronological 70/15/15 split, training-only standardization, fixed L2=1 logistic regression and 0.5 classification threshold as PHASE4_PROTOCOL.md. Minimum post-purge train/validation/test counts remain 100/20/20. Compare always-up, training prior and five-session momentum on identical test rows. Report accuracy, balanced accuracy, Brier score, log loss, confusion counts and moving-block bootstrap intervals. Do not tune on test outcomes. Probabilities remain uncalibrated.

Keep the existing next-session entry/five-session exit, non-overlapping illustrative long/cash simulation and 0/10/25 bps cost scenarios. No executable-price or profit claims. Archive source, feature, implementation and this protocol hash. Missing history remains visible; feature warmup restarts after gaps. Insufficient rows cause a failed experiment, not an invented score.

This is retrospective exploration of three selected surviving assets. It does not authorize promotion to recommendations, demonstrate market-wide generalization, or complete production validation. Future model selection needs a separate predefined protocol and fresh evaluation data.
