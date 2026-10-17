# Optional free company profiles

Prices and analysis continue to use Twelve Data. Company details use the separate Finnhub Company Profile 2 endpoint only when the user presses **Load company details** inside **About this listing**. No profile request runs automatically, enters AI evidence, or changes price/forecast data.

## Setup

Create a free Finnhub account at https://finnhub.io/ and obtain an API key. In the existing ignored local `.env`, add:

```dotenv
FINNHUB_API_KEY=your-finnhub-key
```

Restart the server. Keep the key on the server; never paste it into chat or frontend code. Existing environment variables take precedence over `.env`. Without the key, the app explains setup and price analysis continues normally.

## Available data and limits

The integration displays company name, Finnhub industry classification, headquarters country, reporting currency, IPO date and an optional external company website. Reporting currency is the currency used in company filings, not necessarily the trading currency. Missing values display as unavailable. Full business descriptions, independently verified sector classifications and ETF objectives, holdings and fees are not provided. Sample accounts never request live profiles.

A response must match the selected ticker exactly and a recognized operating exchange. Nasdaq market segments are not independently verified. Ambiguous or mismatched responses are rejected. Finnhub supplies no profile update timestamp: the displayed retrieval time is the original request time, including on cache hits.

Successful results and empty results are cached in memory for 24 hours, with a 128-entry LRU limit. One provider service instance permits four uncached attempts per rolling minute and pauses new requests for 60 seconds after provider errors. Cached valid entries remain available; expired entries are never substituted after failure. These limits are per process, not a shared deployment quota. Requests have bounded timeouts and no redirects or automatic retries. Provider errors and credentials are not exposed in client error messages.

The local route is `GET /v1/company-profile?asset_id=...`; authenticated account mode uses `GET /v2/research/company-profile?asset_id=...` with its existing authentication and throttling. The browser contacts only these same-origin routes. No CSP or CORS permissions were expanded.

The official endpoint schema identifies Company Profile 2 as the free company-profile endpoint: https://github.com/Finnhub-Stock-API/finnhub-go/blob/master/api/openapi.yaml . Availability, account entitlements and redistribution terms remain subject to Finnhub; a free development key does not establish public redistribution rights. Documentation: https://finnhub.io/docs/api/company-profile2 .

## Verification

Automated tests use synthetic responses and block live provider requests. They cover identity validation, missing fields, sanitized failures, header authentication, bounded caching and request budgets, account isolation, explicit loading and late browser responses. Real-key coverage and data availability must be verified after local configuration; no live Finnhub request was used during implementation.

## Research UI release verification

The stock workspace hides the Crypto navigation link while preserving crypto routes and stored data. Chart type is in the main toolbar. Candlestick mode exposes selected daily open/high/low/close values and a body/wick/color guide outside Advanced. Line mode hides that extra detail.

Monitoring was exercised end to end against the isolated SampleProvider preview: save/open a sample listing, start monitoring, receive a completed check with close date/price and rule status, then stop. No personal watchlist or portfolio was used. This verifies the browser-to-service flow with synthetic data, not continuous live-provider availability. Automated checks also verify stale-data rejection, provider-error shutdown, no automatic retries, rule changes, repeat-match suppression and page-visibility cancellation.
