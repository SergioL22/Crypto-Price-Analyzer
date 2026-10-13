# Research workspace polish

The stock starting state now explains the three-step flow: load listings, choose an asset, explore history. It disappears after a successful analysis and returns when the selection changes. Exchange filters display readable venue names. Saving to the watchlist is disabled until a listing is selected.

Loading controls expose busy states and restore their labels after success or failure. Historical closing prices include their observation date and are distinguished from live quotes. Window returns have a prominent signed value, with color as a secondary cue. Exact indicator tables separate names, values and explanations; horizontal scrolling stays inside the table. Comparison and Settings headings match their navigation labels.

A collapsed prediction-research explanation summarizes Phase 4's lack of consistent advantage over always-up yearly baselines. It does not show a validated forecast, accuracy promise or stock recommendation.

Validation: 85 frontend tests passed, including a new failed-load recovery test that verifies no automatic retry. Browser checks used the isolated sample-data preview, not live providers. Stocks, Crypto, Compare, Watchlist, Portfolio, Alerts and Settings fit the narrow viewport without page overflow; no JavaScript console errors were observed. Portfolio saves, backups, alerts and paid AI calls were not exercised in the preview. Python/model behavior is unchanged by this polish.
