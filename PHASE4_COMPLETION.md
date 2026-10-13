# Phase 4 research implementation complete

Phase 4 now includes the reproducible retrospective experiments, expanded stock/ETF evaluation, and manual prospective prediction journal. This completes the research tooling and predefined historical experiment. It does not complete production prediction validation: no model has passed the promotion gate and there are no real prospective outcomes yet.

## What was delivered

- Retained the earlier Bitcoin/Ethereum and AAPL/IBM/SPY experiments and their limitations.
- Captured the fixed ten-asset universe with roughly a decade of split-adjusted stock/ETF history; recorded coverage, identities, immutable source/feature hashes and the missing October 12 session.
- Evaluated 2021–2025 and partial 2026 separately for every asset: 60 expanding-window blocks, with purged five-session labels, training-only scaling, fixed logistic regression and four matched methods (logistic, always-up, training prior, momentum).
- Archived individual probabilities, true outcomes, accuracy/balanced accuracy, Brier score, log loss, confusion counts, class balance, block-bootstrap accuracy intervals and illustrative executions at 0/10/25 bps costs.
- Added equal-weight asset summaries without selecting favorable assets or years, a frozen input manifest and reproducible content-addressed report generation.
- Added an explicit manual append-only prediction journal, separate from portfolio and dataset storage, with model/input/feature/protocol/implementation hashes and exact five-session targets.
- Added later outcome recording, baseline comparisons, per-asset prospective metrics, descriptive calibration bins and integrity verification. No automatic promotion or background tasks.

## What the results mean

The model's equal-weight yearly accuracy was 56.32%, 47.32%, 55.43%, 57.29%, 57.80%, and 52.75% for 2021 through partial 2026. Always-up accuracy was higher in every yearly summary. Balanced accuracy was approximately 49–50.5%. The experiment does not show a reliable directional advantage. Predictions remain uncalibrated, and no accuracy badge or prediction-driven BUY/SELL recommendation was added.

These are retrospective results for a selected surviving universe, not future success rates. Overlapping targets and correlated assets limit independence. Dividends are excluded and source history is present-day adjusted data rather than historical vintages. See `PHASE4_EXPANDED_RESULTS.md` for every asset/block and the full report identity.

## How to operate

Activate the project virtual environment or use its Python directly. All Phase 4 commands below are offline. Only the existing explicit dataset capture command contacts the configured stock provider; no command calls an LLM.

```powershell
# Reproduce the archived historical experiment from the local dataset store.
.\.venv\Scripts\python.exe phase4_cli.py evaluate --audit PHASE4_FROZEN_INPUTS.json --output "$env:TEMP\phase4-reports"

# Inspect real prospective counts (currently zero; no accuracy invented).
.\.venv\Scripts\python.exe phase4_cli.py journal

# Capture a fresh snapshot explicitly; save its returned ID.
.\.venv\Scripts\python.exe dataset_cli.py capture stock twelvedata:stock:XNGS:USD:MSFT --days 3653

# Replace NEW_SNAPSHOT_ID with that returned snapshot ID.
.\.venv\Scripts\python.exe phase4_cli.py issue --snapshot NEW_SNAPSHOT_ID

# After all five target sessions have completed, capture another snapshot
# containing the origin and all target sessions. Then use both returned IDs.
.\.venv\Scripts\python.exe phase4_cli.py settle --prediction PREDICTION_ID --snapshot OUTCOME_SNAPSHOT_ID
.\.venv\Scripts\python.exe phase4_cli.py journal
```

Use `--store PATH` before the subcommand for another research store; use `--journal PATH` on journal/issue/settle for another journal. The default ignored journal is `prediction_journal.db` alongside the source. Back up the database while no writer is active. The journal is tamper-evident local storage, not a signed independent timestamp service.

Issuance requires a stock/ETF snapshot captured within the last 24 hours and after the latest session close, every expected session present, current completed-session features, and at least 500 completed training targets. The model fits using completed labels only; it does not use the future outcome being predicted. Duplicate asset/session predictions are rejected. No CLI backdating option exists. The saved October 12 capture lacks that day's bar, so it is intentionally rejected for issuance.

Target dates use the exchange calendar, including holidays and special closures. Outcome scoring waits for target completion, requires the same asset/adjustment and every target date, and rejects a revised origin price rather than silently changing the original prediction. Predictions are never overwritten: each outcome is a separate hash-linked event. SQLite triggers prevent normal updates/deletes, and chain verification detects external corruption.

## Validation and next phase

392 offline Python tests and 84 frontend tests passed. New coverage verifies year-boundary purging and execution limits, unchanged training fits after future-data perturbation, insufficient-sample rejection, real exchange-calendar target dates, stale/incomplete input rejection, duplicate prevention, delayed settlement, origin revisions, append-only enforcement, hash-chain integrity and absence of CLI backdating.

The next work can polish the product and make these research limitations/results easier to inspect. Prediction integration remains gated on sufficient newly issued and completed outcomes, baseline advantage, calibration and stability across assets/regimes. Fresh outcomes require actual future sessions; synthetic tests and old historical forecasts never count toward that gate.
