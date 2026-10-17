# Expanded selected-list discovery and screening contract

## What users can do

Use Explore's catalog search and asset/exchange/name filters to find supported listings. Open Compare, select up to five companies or ETFs, and choose YTD, approximately one month (30 days), six months (183 days) or one year (365 days). Refresh explicitly. The comparison uses one serial history request per listing, no retries, and stops after a data error to preserve provider quota. A newly selected period clears old results and requires refresh.

Result cards emphasize percentage price changes, actual baseline/end dates, current close and average daily share volume. Sorting supports best/worst period return, volume and closing price. **Filter results** narrows the already loaded rows by stock/ETF type, minimum/maximum close, minimum percentage return and minimum average share volume. Filter/sort changes make no market requests. Counts explicitly distinguish visible results from available selected rows. The entire market is not being screened.

## Baselines and unavailable results

YTD compares the prior-year final returned trading close with the latest completed session. Rolling periods anchor the target to the latest completed session and choose the last available close at or before that target; actual dates are shown. Average volume excludes the baseline session. Complete requested coverage, a usable baseline, positive finite prices, valid share volume and matching baseline/end dates across successful rows are required. Invalid, missing or inconsistent history is reported unavailable; no substitutes, interpolations or inferred fundamentals are used. Returns use one provider split-adjustment response per listing and exclude dividends, fees and taxes. These are historical price changes, not recommendations or model accuracy.

## Replaceable provider contract

`static/assets/screening-feed.js` separates data acquisition/metric validation from `screener.js` rendering and filters. `selectedHistory(request)` is the current adapter. `screen({listings, period, onRow, isCurrent})` returns capabilities, normalized rows, a complete/partial/cancelled state and shared baseline/as-of dates. It discards invalidated requests before publishing results or requesting another listing.

Capabilities declare provider, universe (`selected_list`), maximum listings, periods, supported metrics and unavailable fields. A successful row includes id/name/asset class, period, baseline date, as-of date, return fraction, average daily share volume, closing price, retrieval time and cache flag. Revenue, market capitalization and industry are explicitly null because the current adapter does not supply them. `ytd_return` remains a compatibility alias only in YTD mode; new ranking logic uses `return_fraction` for every period.

A future paid adapter must declare its own coverage and entitlements, validate security identities, dates, units and missing values, and return this normalized format. Market-wide coverage, revenue and industry metrics require real provider data and a corresponding explicit UI capability change; they cannot be activated merely by relabeling this selected-list feed. Fiscal period, reporting currency and update timestamps must accompany any future revenue figures. No paid key, subscription, automatic provider switch or fabricated dataset is included here.

## Verification

550 Python tests and 169 frontend tests passed. New checks cover selected-universe limits, period baselines, missing/nonfinite data, matched dates, cancelled work, result-filter validation and zero extra filter requests. A local synthetic-provider browser check completed a monthly comparison and a minimum-price filter, with no page overflow at 390 px. No personal portfolio, LLM or paid-provider call was used. Local app runtime was not restarted; only an isolated preview server was used and stopped.

Prediction evaluation remains separate and cannot complete before the October 19, 2026 final target session closes. Public access, real accounts and cross-device sync remain later milestones.
