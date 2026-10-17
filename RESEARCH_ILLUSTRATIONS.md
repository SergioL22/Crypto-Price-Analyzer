# Research-only stock workspace

## Watchlist performance

New browser-local saves record a UTC `saved_on` date. Existing entries and backups stay intact; an entry without a date offers an explicit **Start tracking from today** action. No historical save date is inferred. Duplicate saves do not reset tracking.

Expand **Performance since saving** and press **Load performance**. It loads one history response and compares the first completed exchange session after the recorded UTC date with the latest completed session. Consequently a new weekend save may not have a baseline until the next trading session closes. It shows per-share dollar and percentage change and a closing-price graph. Both endpoints use the same provider split-adjustment basis; the baseline can be restated after corporate actions. This is price performance, not dividend-inclusive investment performance.

Incomplete/stale history, invalid prices and unavailable starting periods produce a visible error instead of a fabricated result. Tracking supports up to ten years. Older dates require a future archive/provider extension. Loading is explicit; there is no new background task or AI request. Removed or changed entries discard late results. The local backup/restore path preserves valid dates. Account imports preserve optional dates without altering old backup shapes; this release does not add the performance panel to the separate account research page.

## Investment Simulator

The Portfolio navigation label is now **Investment Simulator**; its URL remains `/portfolio.html` for compatibility. Choose a saved stock or ETF, an imaginary USD amount and a historical start date. The baseline is the first available completed session on or after the date; missing requested trading sessions are rejected. The calculation permits fractional split-adjusted equivalent shares and compares endpoint prices on one adjustment basis.

An optional second saved listing is a benchmark chosen by the user. Both simulations use the same starting amount and exactly matching session dates; mismatches fail closed. One history request is used per distinct listing, serially, with no automatic retry. Changing inputs discards in-flight results. The value graph is an illustration of the hypothetical position, not an account balance or forecast. Dividends, fees, taxes and slippage are excluded. No positions or trades are created. The previous manual position editor is retained under **Advanced: saved hypothetical positions** to preserve existing data.

## Discovery and free-data boundaries

Existing name/ticker, stock/ETF, exchange and alphabetical discovery filters remain available. Compare now supports worst as well as best YTD price performance, highest average share volume and latest closing price. The ranking covers only the up-to-five selected comparison listings, not all listed securities. YTD uses the prior-year closing baseline and matching latest sessions. Revenue ("top grossing"), market capitalization and catalog-wide industry screening remain unavailable with the current free feeds; company-profile lookups do not establish a complete fundamentals catalog. A paid screening feed can later provide the existing normalized ranking contract.

## Research positioning and verification

The app remains research-only: no order placement, brokerage execution or movement of money. Historical scenarios and price changes are not model accuracy or predictions. Existing AI evidence boundaries are unchanged.

Verification: 524 Python tests and 155 frontend tests passed, including arithmetic, stale/missing coverage rejection, date validation and migration, benchmark date matching, changed-input responses, explicit loading and limited-list ranking. An isolated sample-provider browser run completed an investment illustration, comparison and graph; legacy watchlist tracking prompts were checked. No real keys, personal portfolios or paid providers were used for these checks. The user's local app was left stopped.
