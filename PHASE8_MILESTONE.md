# Phase 8 local research milestone

## Delivered

- Automatic stock/ETF catalog loading and chart loading on listing selection, with stale-response protection.
- Local exact-ticker filtering, exchange/name/symbol sorting and clear filters.
- Bounded five-minute history cache with provenance, explicit refresh, provider-error cooldown and an interactive six-attempt rolling-minute budget per service instance.
- Foreground watchlist monitoring, sequential target checks, new/continuing match labels and freshness details. Monitoring is opt-in and stops on hiding/navigation/errors.
- Provider-independent OHLCV validation before caching and analysis, including duplicate dates, invalid values and impossible price ranges.
- Shared professional charcoal UI, restrained blue accents, prominent prices, compact actions and responsive layouts.

## Verification

488 Python tests and 124 frontend tests passed locally. Offline guards block live provider calls in the Python suite. Browser checks used synthetic sample data at desktop and 390-pixel phone widths. GitHub CI must additionally confirm the published commit on both operating systems and Python versions; local results alone do not confirm CI.

## Limits and next steps

This is a single-user local research milestone, not a public hosted release. Monitoring uses completed-session closes and has no closed-app/email/push delivery. Browser watchlists remain local. The request budget is per service instance, not a distributed credit ledger. Company fundamentals and market-wide rankings still require suitable data coverage. Historical and prospective prediction evidence must remain separate, and confidence is not measured accuracy.

Next: confirm publication and all six CI jobs, then improve company/fund discovery and summaries within clearly labeled free-provider coverage. Paid data, licensing, hosting, real accounts and background delivery require separate preparation. The pending prospective batch remains unchanged and must not be scored before its final October 19 target-session close.

## Recovery

The checked installer stores versioned source backups under the task outputs directory. Runtime databases, local keys, portfolio files and immutable research records are excluded from the milestone. Publishing must preserve them. Roll back code through a reviewed revert rather than deleting runtime data.
