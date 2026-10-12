# Stocks-first workspace — 2026-10-07

The home page now opens Stocks & ETFs. Crypto remains a separate `/crypto.html` page; existing crypto watchlist links point there. `/stocks.html` remains a supported alias. No crypto holdings, alerts, database or backups were migrated or rewritten.

## Use the new workflow

1. Start the backend in the terminal containing `TWELVE_DATA_API_KEY`, using `python -m uvicorn backend:create_app --factory --host 127.0.0.1 --port 8000`. Restart an older backend to enable the expanded history limit.
2. Load the stock or ETF catalog. Search names/symbols and optionally select an exchange. Choose a listing and research it.
3. History defaults to 3,653 calendar days (roughly ten years, covering leap days). Presets include one month, six months, YTD, one year, five years and ten years; custom windows support 1–3,660 days. These are calendar-day windows, not exact month anniversaries. Provider requests retain a 5,000-row cap, above the roughly 2,500 daily sessions in a decade.
4. The chart states the returned date range and expands missing-session details on demand. Its first returned date is NOT asserted to be the IPO date. Partial access, newer listings and provider omissions cannot be distinguished reliably without additional metadata. Incomplete coverage continues to suppress indicators rather than calculating across gaps.
5. Save the selected listing to the stock/ETF watchlist. Its link preselects the listing after you explicitly load the matching catalog; it does not fetch analysis automatically.
6. Add up to five listings to a comparison and click Refresh comparison. Sort by YTD price return, average daily share volume this year, or latest closing price. YTD requires complete coverage including the prior year's closing baseline. Results display their as-of date. An error stops remaining requests and labels partial output. No retries or whole-catalog scan occur. The comparison list is tab-local and resets on navigation.

## Holdings, alerts and backups

Stock/ETF watchlists, holding snapshots and alert rules share a separate versioned browser-local store, `research-desk.equities.v1`. Up to 50 of each are supported. They are not account-synced, shared with the CLI or written to the crypto portfolio. They are tied to this browser/site address, including its port. Clear-site-data removes them. Export and restore them on Backups; crypto backups remain separate.

Portfolio: choose a saved listing, enter total shares and average cost, then save. Valuation explicitly requests one holding's most recent available completed-session price and labels its date/staleness. Cost differences exclude dividends, fees and taxes; zero cost means unknown. Quantities/costs are snapshots and must be updated after trades or splits. This is not automatic corporate-action accounting or a consolidated cross-asset portfolio valuation.

Alerts: save a strict above/below closing-price or RSI threshold, then explicitly check one listing. No live intraday monitoring, background scheduling or push/email notifications. An unavailable latest session leaves alert state unchanged; unavailable RSI retains that rule's state. Repeated matches are suppressed until a valid check clears the condition. The UI shows results of the current check; this initial stock workspace does not maintain a durable trigger journal or pause/resume feature.

Backups: download stock workspace JSON, then preview and confirm replacement to restore. Invalid files or a workspace change since preview prevent replacement. Export current contents first if they must be retained. Files contain holdings and should be kept private. Browser storage is not encrypted by the app or a transactional multi-user database; server-backed synchronization remains future work.

## Free now, paid later

User choice: keep current operation free, plan for a smooth paid-data transition. No paid endpoints, new subscription or account upgrade was enabled.

The current catalog filters are asset class, name/symbol and exchange. Ranking is explicitly restricted to selected listings. Annual revenue, market capitalization, sector, dividend yield and ETF expenses need additional data sources; the interface does not invent those values or label a small comparison as the market's top performers.

The comparison renderer consumes rows with `id`, `name`, `as_of`, `ytd_return`, `average_volume`, `price` and optional `unavailable`. Keep this contract when adding a server-side paid screening adapter. The current renderer and calculation live in `screener.js`; the future paid adapter itself is not implemented. Upgrading Twelve Data history entitlements uses the existing server credential and identity scheme, so saved listings do not need changing.

Before enabling paid discovery: implement a capability response with supported filters and universe/coverage, map new provider identifiers explicitly, preserve saved provider-qualified IDs, normalize fundamentals with reporting-period dates, and add quota/cost controls. Switch the data source behind the existing controls; do not silently upgrade or send requests to paid endpoints. A different provider may require verified identifier migration. Upgrade compatibility is planned, not a claim that every future provider is plug-and-play.

Provider references checked October 7, 2026:
- [Historical date ranges and daily history](https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices)
- [5,000-point limit and date filtering](https://support.twelvedata.com/en/articles/5214728-getting-historical-data)
- [Plan limits and endpoint credit costs](https://twelvedata.com/pricing)

## Verification

375 Python tests and 64 JavaScript tests passed offline. New coverage includes decade windows, partial-history withholding, qualified browser watchlists, storage isolation, stale valuation rejection, alert freshness and duplicate handling, restore conflicts and YTD calculation/coverage exclusions. Existing route/initialization checks now include the separate crypto page. Two existing dependency deprecation warnings remain.

Browser smoke test used an isolated fake-provider server on port 8001: 2,513 complete daily samples rendered for the decade, YTD comparison completed, a sample holding was saved/valued, and a price alert triggered. All six pages fit a 390px viewport without horizontal overflow. Test records were confined to the separate preview origin. No real holdings were edited and no provider/LLM charges were incurred.

Live ten-year provider acceptance remains unverified without an authenticated server. This change does not extend the separate research-dataset capture CLI's 364-day limit or retrain prediction models. A follow-up stock training-data expansion must define provider entitlements and research coverage explicitly. Changes are local, uncommitted and unpushed.
