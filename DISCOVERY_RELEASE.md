# Discovery and simplified research release

## Delivered

- Visible stock/ETF selection, multiword/accent-tolerant search, alphabetical filters, exchange catalog counts and metadata-only listing explanations.
- Compact search area, quiet status messages, expandable listing information and technical indicators, and a chart toolbar focused on history range/fullscreen.
- Automatic analysis after a requested history-range change, with pending changes coalesced to the latest selection. Successful research scrolls to the price/chart, respecting reduced motion; Change listing returns to search.
- Manual recovery for catalog failures even when Filters is closed.
- Compare no longer starts hidden standalone analysis requests on listing/range selection or form submission. Comparison loading remains explicit.

## Verification

488 Python tests and 137 frontend tests passed locally. The prior synthetic-provider browser checks verified desktop/390-pixel layouts, access to advanced tools, changing the selected range and returning to search. Public CI still must confirm the published commit across its six jobs.

## Scope

Listing summaries use catalog metadata only; verified company business profiles, sectors, ETF holdings/fees and full-market rankings are future data work. This release does not create accounts, change provider plans, invoke paid AI automatically, place trades, settle predictions or modify journal origins. Existing provider identity checks, caching, request budgets and data validation remain in force.

## Operation and recovery

Hard-refresh the browser after installing. The checked publishing script verifies reviewed source hashes and the Git bundle, checks remote main, pushes without force, saves backups, synchronizes the original checkout and checks CI. Local credentials, SQLite files, saved positions and other runtime data are excluded. Code can be recovered from the release Git bundle or reverted through normal Git history.
