# Public filings research (SEC EDGAR)

Added November 4, 2026. Not yet published or deployed.

The public demo can serve a real-data research page at `/filings-research.html` without any market-data license. Every value comes from public SEC EDGAR filings. The SEC treats its site content as public information that may be copied or further distributed without permission ([SEC dissemination policy](https://www.sec.gov/about/privacy-information)). No stock prices are used, so the page stays outside the price-provider restrictions described in `APP_RELEASE_PLAN.md` and `FREE_DATA_PERMISSION_REQUEST.md`.

## What visitors get

- **Company fundamentals** for the nine starter stocks: up to ten fiscal years of revenue, operating income, net income, operating cash flow, capital expenditure, diluted EPS and diluted share count from XBRL `companyfacts`. Each value links to the filing it came from. Free cash flow and operating/net margins are labelled as calculated.
- **Recent filings**: the latest 10-K, 10-Q, 8-K, Form 4 (insider), proxy and 13D/G filings, linked to EDGAR.
- **ETF holdings** for SPY, QQQ, IWM, DIA and VTI from each fund's latest public Form N-PORT. Shows holdings count, top-10 weight, effective number of holdings (1 ÷ sum of squared weights) and net assets.
- **ETF overlap**: overlap by weight (for each shared security, the smaller of its two weights, summed) and how much of each fund's weight the other fund also holds. Securities match by ISIN, then CUSIP.

Short positions and short-term cash vehicles (N-PORT asset category `STIV`, such as reinvested securities-lending collateral) are excluded from holdings and overlap. Their weight is shown separately.

## How it runs

The web app never calls the SEC. `sec_refresh.py` builds `sec_data/research_snapshot.json` (about 1 MB), and the demo serves it read-only from memory. This keeps visitor traffic away from EDGAR, works on Render's ephemeral free filesystem, and keeps the offline test suite offline.

Routes (only when `PUBLIC_SEC_RESEARCH=1`, which `render-demo.yaml` sets): `/v1/sec/coverage`, `/v1/sec/company?symbol=`, `/v1/sec/fund?symbol=`, `/v1/sec/overlap?a=&b=`. Responses carry `X-Research-Data: sec-public` and `Cache-Control: public, max-age=3600`. The existing origin, method and request-budget checks still apply. With the flag unset, the routes and page return 404 and the synthetic demo is unchanged.

## Refresh the snapshot

The SEC asks automated clients to identify themselves with an app name and a contact email, and to stay under 10 requests per second ([fair access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)). The script waits 0.15 s between requests.

```powershell
$env:SEC_USER_AGENT = 'ResearchDesk/1.0 (your-email@example.com)'
.\.venv\Scripts\python.exe sec_refresh.py
```

Then run the tests, commit the updated snapshot and redeploy. N-PORT holdings are published about 60 days after each fiscal quarter, so a monthly refresh is enough.

**Automatic refresh:** `.github/workflows/sec-refresh.yml` runs this on the 3rd of each month (and on demand from the Actions tab). It validates the result with the SEC tests and commits the snapshot only when the SEC data actually changed. A rebuild that differs only in its build time is not rewritten. Add a repository secret named `SEC_USER_AGENT` (Settings → Secrets and variables → Actions) before the first run.

Notes:
- **XOM**: Exxon Mobil's listing now files as ExxonMobil Holdings Corp. The refresh merges the predecessor registrant's (CIK 34088) annual values and filings, and the page says so.
- **Multi-series trusts** (iShares Trust for IWM, Vanguard Index Funds for VTI) are looked up by fund series ID. The refresh fails if the filing does not cover that series.
- **Fiscal years** use the SEC's calendar-year frames, which pick one de-duplicated annual value per company per year. Labels use the fiscal-year end date, so NVIDIA's year ending January 2026 shows as FY2026.
- Banks and some other companies do not report every measure under the standard tags (for example, JPMorgan has no operating income or capital expenditure). Those charts say so rather than estimating.

## Filing alerts

The top of the page lets visitors follow any of the covered companies and choose filing types: reports, material events (8-K), insider trades (Form 4), and ownership, proxy and offering filings. Followed companies default to the visitor's market watchlist. Filings filed since the visitor last pressed **Mark all as seen** get a NEW badge. When a company is first followed, its existing filings count as seen, so only later filings are flagged. Choices and seen markers stay in that browser (`research-desk.filing-alerts.v1`). The check runs when the page opens or on **Check now**. There are no background jobs, emails or push notifications.

`/v1/sec/filings?symbols=AAPL,MSFT` returns up to 20 recent filings per company with `filings_source` (`live` or `snapshot`) and `filings_fetched_at_utc`. `/v1/sec/company` uses the same source.

- **Live filings** are on only when `SEC_USER_AGENT` is set (app name and contact email). The server then fetches each company's `submissions` feed at most once every 30 minutes and backs off for 5 minutes after a failure, so visitor traffic never reaches EDGAR. On Render, set it under the service's Environment settings. `render-demo.yaml` lists it with `sync: false`, so it is never stored in the repo.
- **Without it**, or when EDGAR is unreachable, filings come from the committed snapshot, and the page says which source and time it is showing. Live rows are merged with the snapshot's, which keeps XOM's predecessor filings.
