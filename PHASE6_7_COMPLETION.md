# Phases 6 and 7 — implemented October 14, 2026

The Phase 6 validation tools and Phase 7 account research/assessment experience are implemented and covered by automated tests. Collecting enough future outcomes and rendered visual acceptance remain open; these cannot truthfully be called completed model validation or mobile usability testing.

## Phase 6: validation infrastructure

`prediction_validation.py` reads the verified append-only journal without modifying it. It reports pending/completed counts, the next target end, the five-session direction definition and exact cohorts. Once outcomes exist, it compares the model with always-up, training-prior and momentum using the same observations, with accuracy, balanced accuracy, Brier score, log loss and confusion counts. Asset and quarterly breakdowns expose uneven coverage.

Different protocol/implementation hashes stay separate. Parallel assets and overlapping windows are counted explicitly. Paired Brier comparisons weight retained nonoverlapping start dates equally; exploratory uncertainty intervals are unavailable below 20 dates. Fixed calibration bins show observed frequencies without claiming the model has been calibrated. See [the reporting protocol](PHASE6_VALIDATION_PROTOCOL.md) for assumptions and limitations.

Current real state: **10 predictions, zero completed outcomes, 10 pending; next target end October 19**. The scheduled follow-up waits for that close and complete provider data. Reliable stock-specific accuracy, calibration and performance across regimes require further prospective collection and review. No model was retrained or promoted.

Run from the Crypto project directory:

```powershell
.\.venv\Scripts\python.exe prediction_validation.py
```

`--asset` restricts the report to a provider-qualified asset ID; `--journal` selects an explicit journal and `--output` writes a JSON report. The account app also exposes authenticated, throttled, read-only validation through `/v2/research/validation`. Managed deployments leave this local research access disabled.

## Phase 7: evidence, reasoning and measured results

In the **separate account research app**, run analysis, then use the new Reasoning and prediction results section:

1. The existing price/chart and explained indicators describe historical observations.
2. **Get AI recommendation** provides BUY/HOLD/SELL reasoning and qualitative evidence confidence. Reasons and risks show their cited evidence keys and exact values; a collapsed full-evidence table includes the illustrative backtest. Confidence is explicitly not measured accuracy or a probability of profit.
3. **View validation results** reads actual stock/ETF prediction outcomes. It never invents a percentage when there are no outcomes. Model/baseline results, calibration diagnostics, counts and limitations stay separate from AI reasoning. Crypto validation is not supported by the current stock/ETF journal.

The illustrative RSI/moving-average backtest uses the same loaded prices; zero closed trades produce unavailable win-rate/average-return fields rather than a misleading 0%. Same-close signal/fill assumptions are optimistic, and fees, slippage and dividends are excluded. Asset drawdown is not strategy-equity drawdown. No position sizing, automatic orders, price targets, news or fundamental claims are supplied.

## AI request integrity and privacy

- Analysis creates a signed, session-bound token that expires after ten minutes. A recommendation uses the exact evidence from that token rather than refetching a different window. A newly closed session invalidates stale evidence. Tampered tokens, other sessions, incomplete history, missing CSRF and expired sessions are rejected.
- OpenAI is called only on the explicit button action in private live mode, with no automatic retries. One provider call is admitted at a time; account and token throttles bound repeated clicks. Provider failures preserve raw analysis and return sanitized diagnostics.
- Portfolio context is off by default. Checking the disclosure sends only the selected asset's shares and average cost from the current account. Names, account identity, session/CSRF values, other positions and alert rules are excluded from the provider payload. The complete returned evidence makes inclusion auditable.
- The existing Responses structured-output contract is reused. Known evidence keys and response structure are validated; this does not prove that every LLM claim is factually correct. Users still need to compare the reasoning with the cited values. [Official OpenAI structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
- Synthetic mode returns a clearly labeled offline illustration and makes no OpenAI call. Sign-out, session expiry or selection changes clear/discard displayed and in-flight assessment results.

## Try it

From the project directory, start one factory on port 8001:

```powershell
# Offline sample analysis and assessment illustration
.\.venv\Scripts\python.exe -m uvicorn account_backend:create_staging_app --factory --host 127.0.0.1 --port 8001 --workers 1 --no-access-log --no-proxy-headers
```

```powershell
# Real provider history and explicit OpenAI assessments; uses ignored .env
.\.venv\Scripts\python.exe -m uvicorn account_backend:create_local_research_app --factory --host 127.0.0.1 --port 8001 --workers 1 --no-access-log --no-proxy-headers
```

Open http://127.0.0.1:8001/, choose a sample account, load listings, select an asset and run analysis. Live AI requires the existing OPENAI_API_KEY and OPENAI_MODEL settings and may incur charges. Use synthetic positions only: sample profiles are not real authentication and anyone on the local machine can open them. These factories must remain loopback-only. The original app on port 8000 is separate; its existing recommendation flow is preserved.

## Verification and remaining work

- **444 Python tests and 109 frontend tests pass**. New tests cover report cohorts, baseline parity, date dependence, calibration boundaries, token expiry/tampering, CSRF, opt-in selected-position isolation, invalid citations, sanitized failures and logout during provider calls. Client tests cover explicit requests, duplicate blocking, zero-outcome states and stale-response clearing.
- The real journal was independently read: 10 pending and zero completed. No premature settlement or accuracy claim was made. Synthetic prediction tests are not real validation evidence.
- The OpenAI path was tested with offline provider doubles and the existing HTTP-adapter regression suite. No new charged live OpenAI smoke test was run.
- Responsive columns, contained detailed tables, keyboard focus styles, status announcements, 44-pixel summary targets and a collapsed glossary were added. Rendered browser acceptance was completed on October 15 at 1440, 768, 390 and 320 pixel viewport widths. Page-wide horizontal overflow was absent, including with the 2,512-observation table open. Checks covered stock/ETF/crypto selection, offline sample AI citations, zero-outcome validation, candlesticks, fullscreen/Escape, ETF watchlist saving, and account-switch clearing. Synthetic preview data was isolated from real portfolios. A mixed Windows apostrophe encoding in the consent label was normalized to UTF-8. These checks do not replace physical-device or live-provider acceptance.
- Real accounts, hosted deployment, provider display licensing and ongoing automated issuance remain later work. This guide accompanies the Phase 6/7 publication milestone; see Git history and CI for its publication status.
