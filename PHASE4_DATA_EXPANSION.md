# Phase 4 dataset expansion and validation

`research_universe.py` implements the collection and coverage checks preceding the next model experiment. It follows `PHASE4_NEXT_PROTOCOL.md`: MSFT, JNJ, JPM, XOM, QQQ, IWM, DIA, with previously evaluated AAPL, IBM and SPY retained as controls. The list cannot change from the command line. The current selected universe does not represent all securities or avoid survivorship bias.

## Run

From the project directory:

```powershell
# Offline audit of the latest saved snapshot for each unambiguous listing.
.\.venv\Scripts\python.exe research_universe.py --report "$env:TEMP\universe-audit.json"

# Explicit live capture: loads the existing local .env without printing keys.
.\.venv\Scripts\python.exe research_universe.py --capture --report "$env:TEMP\universe-audit.json"
```

Use `--store PATH` for a separate research database. The default is the ignored `research_datasets.db`; this command does not access portfolios, the crypto runtime database or OpenAI. Keep output JSON outside tracked source files. Exit code 1 indicates incomplete collection/audit or a command failure; inspect the report rather than assuming every asset succeeded.

Live collection resolves exact listing IDs from a fresh catalog and requests 3653 calendar days per asset. Ambiguous or missing listings remain explicit failures. Requests are spaced by ten seconds, run sequentially, and are never automatically retried. Quota, key-setup or access failures stop subsequent captures. Successful captures retain immutable artifacts even if later assets fail. A failed live capture never falls back to an older snapshot. Provider credits are shared with other running applications, so pacing cannot guarantee quota availability.

Offline mode uses saved snapshots only. It chooses the newest capture for each unique provider-qualified listing, not the snapshot with the most favorable coverage or returns. Multiple saved venue identities are flagged for resolution. Missing assets remain visible. Offline reports include capture time and collection settings; they do not assert that older data is fresh or that a shorter snapshot contains a decade.

## Report

Each asset records exact identity, immutable snapshot and feature IDs, observed dates, expected/observed session counts, all missing dates, unknown volume, and supervised row counts. Features retain the existing causal eight-column daily-v1 definition and a five-session target. Gaps restart feature warmup and prohibit labels crossing the missing sessions.

For each 2021–2025 full-year block, the audit requires 500 earlier training rows and 100 completed test targets. Training labels must end before the first eligible test feature date; test labels must end within that calendar year. Partial 2026 is explicitly labeled and requires 500 training rows and at least one completed test target for computational eligibility. That minimum is not enough for a reliable accuracy claim. Counts do not constitute a fitted model or evaluation result.

Snapshots are present-day provider history, not historical point-in-time vintages. Split-adjusted prices exclude dividends. Missing dates, incomplete history, provider entitlements, current-universe selection and known prior control results remain attached to the experiment. No predictions, model promotion, automatic collector, or recommendation integration is included here.

The next step is to evaluate the frozen artifacts against the predefined baselines with the protocol's yearly splits, uncertainty measures and cost scenarios.
