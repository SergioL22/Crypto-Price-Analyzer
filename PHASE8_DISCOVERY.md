# Phase 8, step 1: discovery and history-fetch reliability

Implemented October 15, 2026. This is the first Phase 8 increment; The October 16 increment below adds foreground watchlist monitoring; broader data-quality work and a paid screening feed remain future work.

## What changed

Both the original Stocks & ETFs home page and the separate account research app now offer an exact-ticker/provider-ID search mode, sorting by name/symbol/exchange, and a clear-search-filters button inside the existing filter controls. Search, sorting and exchange filtering operate on the already-loaded catalog and make no additional provider requests. Listings are not presented as market-wide revenue or performance rankings. The original Compare page still ranks only the user's explicitly selected comparison list by historical price performance/volume, with its existing coverage rules.

Stock/ETF browsing now opts into a bounded in-memory history cache. Defaults are five minutes and sixteen exact listing/window entries per StockService instance. Repeating an analysis can reuse its daily bars while recalculating indicators and coverage from copied data. Results say whether a history fetch was reused; original fetch time and cache age at request are available in data-coverage details. These are historical observations, never a live quote.

The cache key includes provider-qualified identity, requested start/end dates, the latest eligible completed session and split-adjustment basis. A changed window, exchange, asset, or newly completed session cannot reuse the wrong entry. Cache results are defensive copies, and old entries are evicted. Gaps stay explicit and suppress indicators/AI eligibility as before. An incomplete response can remain cached for up to five minutes; the user can explicitly refresh it.

The **Fetch fresh history on next analysis** checkbox bypasses cache reuse on the next analysis request (including a user-selected listing). It uses provider quota, does not start a request by itself and does not clear the existing chart merely when checked. Account sign-out clears the opt-in, and crypto disables this stock/ETF control. Crypto fetch behavior is otherwise unchanged.

After a history provider error, interactive history misses/forced refreshes pause for sixty seconds by default. The response includes a Retry-After header; the browser makes no automatic retry. A still-valid exact-window cached entry can be read during that pause, with its original provenance. Expired data is never substituted after an error. Catalog refresh has its own existing cache/retry behavior; this is not a shared multi-worker or account-wide provider credit ledger.

## Research safety

StockService.research defaults to `use_cache=False`. Dataset capture, prospective issuance inputs and outcome capture therefore retain fresh-fetch behavior. Only the interactive HTTP/research adapters opt in to caching. Regression tests fill the browsing cache, then capture the same research window twice and verify that each capture calls the provider again. No dataset/journal format or prediction protocol was changed.

The AI snapshot includes the history-source metadata, so the returned full evidence records cache provenance. Existing session-bound signing, expiry and latest-completed-session checks remain in force. No LLM/provider request runs just from searching or sorting; this development/QA work used synthetic data and no paid calls.

## Configuration and provider upgrades

StockService accepts `history_ttl`, `history_capacity` and `error_cooldown` constructor settings. The existing provider catalog/history interface, qualified asset identities, OHLC units and adjustment basis are preserved. Upgrading Twelve Data entitlements can continue using that interface; public display rights, provider access and real screening coverage still need separate verification. No subscription is purchased or entitlement inferred by these changes. Cache storage is public market data in process memory, separate from account positions and immutable research artifacts; restart clears it.

The history endpoints accept optional `refresh=true` (`/v1/stock-analysis` and `/v2/research/analysis`). Responses add `history_source` with cache_hit, fetched_at_utc and age_seconds. The account endpoint retains authentication, rate limits and signed analysis tokens. The original server remains a loopback-only, single-user application.

## Verification and operation

- 488 Python tests and 124 frontend tests pass, including repeated-window reuse, expiry, forced refresh, cache isolation, completed-session boundaries, fresh research capture, quota cooldown, partial-window recovery and HTTP metadata/Retry-After behavior.
- Browser checks used synthetic stock/ETF providers. Exact-ticker search, initial fetch, repeated cache hit and explicit refresh were verified on the original home page. Account browsing also showed cache reuse. Both filter panels were checked at desktop/390-pixel phone widths without page-wide horizontal overflow; no browser console errors were observed.
- Changes are prepared in the isolated project copy and are not committed or pushed. Installation uses the supplied checked apply script, which verifies expected source contents and keeps backups; it does not touch .env, databases, positions, journal files or Git metadata. Restart the relevant app after applying, then refresh the browser.

Next Phase 8 steps: hosted/background notification design, stronger provider budget controls, broader history-quality acceptance and genuine screening capabilities when suitable data access is available. Reliable prediction accuracy and real accounts remain separate later acceptance items.

## Automatic listing loading

Stock listings load when the page is ready. Account research listings load after sign-in. Switching markets queues the latest catalog behind any outstanding request; stale responses cannot replace it. Failed loads permit manual retry without an automatic retry loop. Selecting a company or fund now loads its chart automatically, including saved-listing links. Rapid selection changes queue only the newest choice and discard obsolete results. AI assessment remains an explicit action. Changing only a history range still uses View analysis to apply that range.

## October 16: foreground watchlist monitoring

Watchlist and Alerts now have Start/Stop monitoring controls. Monitoring starts only after a click, checks saved watchlist stocks and ETFs in round-robin order, and schedules one listing after each sixty-second interval. It never downloads every listing at once. Both price and RSI rules use strict above/below comparisons; equality clears the match. New matches are distinguished from conditions that still match. No rule means a price card without an invented target.

Cards show the latest eligible close, the session date, local check time and per-rule results. Exact UTC check/fetch timestamps are in Data freshness. Last-check cards are session-only and reset on reload; saved alert conditions remain in the existing browser workspace and backups. A rule or watchlist edit during a request invalidates the result, preserving the user's edited workspace. Unavailable RSI retains the prior rule state with an explicit unavailable message. A stale/missing latest close cannot change alert states.

Monitoring stops on page hiding, navigation, provider failure or invalid storage. It does not resume itself on return, reload or error. A shared local timestamp spaces monitoring attempts across same-origin pages, with Web Locks serializing that claim when supported; without Web Locks, cross-tab coordination is best effort. This is not a server-wide provider credit ledger and manual research checks can also consume quota. The server's five-minute cache and failure cooldown remain in effect. Only completed-session data is used, so intraday target crossings can be missed. No email/push service, closed-app monitoring, AI calls, trades, account-sync, prediction issuance or outcome settlement was added.

The target link on a monitoring card opens Alerts with that saved listing selected. Existing manual alert checks now show a check timestamp too. Browser QA used only synthetic sample-provider prices and a separate preview origin. It verified automatic chart selection, a new threshold match, monitor opt-in after reload, and responsive monitoring cards. Regression coverage includes foreground cancellation, stale-data refusal, no error retries, concurrent edits, pacing and serial listing rotation.

## Interactive history request budget

Each StockService instance limits interactive upstream history attempts to six in a rolling sixty-second window by default. Cache hits do not consume budget, but forced refreshes and failed provider attempts do. Distinct concurrent misses share one lock and budget. A blocked request returns stock_budget, HTTP 429 and Retry-After, without calling the provider or substituting expired data. Browser errors show the wait time; charts and monitoring never automatically retry after that error. Still-valid exact-window cache entries remain usable. Existing provider-error cooldowns also remain in force.

Constructor settings history_request_limit and history_budget_window permit controlled adjustments without changing provider interfaces, asset identities or indicator formulas. This limit covers interactive history within one service instance, not catalog requests, direct research capture, all processes, daily credits or the provider's complete account quota. Six is a conservative application default, not a claim about an entitlement. A real distributed quota ledger remains future work. No provider plan or key was changed.

## Provider-independent history acceptance

StockService validates every returned daily-bar list before caching, chart overlays or indicator calculation. This also protects fresh research capture and future provider adapters. The transport adapter's existing identity and metadata checks remain unchanged. The service rejects malformed rows, missing OHLCV fields, duplicate/noncanonical/out-of-window dates, boolean/nonfinite/nonpositive prices, negative/nonfinite volume and impossible OHLC ordering. Numeric strings are normalized; zero volume is valid. Returned rows are copied and sorted by session date without mutating provider-owned data.

Existing exchange-session checks still reject nontrading days and exclude unfinished sessions. Missing eligible days remain explicit and suppress indicators; no values are invented, interpolated or replaced with stale data. A rejected response cannot populate the browsing cache. This is structural validation, not proof of economic correctness, verified split adjustment, real-time entitlement or point-in-time corporate-action quality. No model, prediction journal, origin price or prospective outcome has been changed.
