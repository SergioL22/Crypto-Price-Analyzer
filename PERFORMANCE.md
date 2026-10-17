# Hosted research responsiveness

Company search now caches normalized catalog fields and reuses an Intl.Collator. Typing coalesces into a search after 120 ms without further input, while stale selection controls are disabled. The complete catalog is still searched; native dropdown DOM nodes are rendered in batches of 200. **Show next matches** exposes all remaining listings without provider calls. Counts explicitly show when only part of the matching list is rendered. Selected and deep-linked listings remain reachable even outside the first batch.

Chart dates are parsed once; hover finds the nearest observation with a binary search instead of reparsing and scanning the entire window on each pointer move. Prices, dates, gap handling and chart calculations remain unchanged. Hosted catalog/history/static responses larger than 1 KB use gzip when the browser supports it. No persistent response cache or relaxed authentication was added.

A synthetic local benchmark of four search/sort queries across 12,000 listings averaged 133.5 ms before and 56.6 ms after this change (five repeated batches). This measures JavaScript matching/sorting only, not actual Render response time, DOM layout or a production latency promise. Tests verify complete-catalog access, paging, rapid-input coalescing and compressed response contracts. All 550 Python and 156 frontend tests passed.

Render Free wake-up time and market-provider response delays remain outside these client optimizations. Existing server caches and provider budgets still apply; no extra background fetches, retries, paid provider calls or infrastructure upgrades were added. A warm-service check after publication is needed to assess perceived improvement in the actual hosted app.
