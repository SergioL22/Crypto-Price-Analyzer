"use strict";
const $ = id => document.getElementById(id);
const el = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
const format = value => value === null || value === undefined ? "N/A" : typeof value === "number" ? new Intl.NumberFormat("en-US", {maximumFractionDigits: 6}).format(value) : typeof value === "object" ? JSON.stringify(value) : String(value);
const resolve = (obj, key) => key.split(".").reduce((value, part) => value !== null && typeof value === "object" && Object.hasOwn(value, part) ? value[part] : undefined, obj);
let revision = 0, analysisSequence = 0, pendingAI = false;
function status(text) { $("status").textContent = text; }
function reset(panel, title) { panel.replaceChildren(el("h2", title)); }
function rows(parent, values) { const dl = el("dl"); for (const [key, value] of Object.entries(values)) { const row = el("div"); row.append(el("dt", key), el("dd", format(value))); dl.append(row); } parent.append(dl); }
function coverage(parent, w) {
 rows(parent, {"Requested UTC dates": `${w.expected_start} → ${w.expected_end}`, "Observed dates": `${format(w.start)} → ${format(w.end)}`, "Observations": w.observations, "Missing days": w.missing_days, "Leading / internal / trailing gaps": `${w.leading_missing_days} / ${w.internal_missing_days} / ${w.trailing_missing_days}`, "Latest observation age (days)": w.latest_observation_age_days});
}
function validEvidence(e) {
 return e && typeof e.coin_id === "string" && typeof e.generated_at_utc === "string"
  && e.window && Number.isInteger(e.window.observations) && Number.isInteger(e.window.missing_days)
  && typeof e.window.expected_start === "string" && typeof e.window.expected_end === "string"
  && e.indicators && Number.isFinite(e.indicators.latest_history_price_usd)
  && e.backtest && Number.isInteger(e.backtest.closed_trades)
  && e.portfolio && typeof e.portfolio.included === "boolean"
  && Array.isArray(e.limitations) && e.limitations.every(value => typeof value === "string");
}
function evidence(parent, e) {
 if (!validEvidence(e)) throw new Error("Invalid response");
 parent.append(el("p", `${e.coin_id} · snapshot ${e.generated_at_utc}`));
 coverage(parent, e.window);
 parent.append(el("h3", "Indicators"));
 const i = e.indicators;
 rows(parent, {"Historical price (USD)": i.latest_history_price_usd, "Live price (USD)": i.live_price_usd, "RSI (14)": i.rsi_14, "Moving average (7)": i.ma_7, "Moving average (25)": i.ma_25, "MACD": i.macd, "MACD signal": i.macd_signal, "MACD histogram": i.macd_histogram, "Bollinger lower": i.bollinger_lower, "Bollinger middle": i.bollinger_middle, "Bollinger upper": i.bollinger_upper, "Historical support swings": i.support, "Historical resistance swings": i.resistance, "Patterns": i.patterns, "Average volume (20)": i.average_volume_20, "Volume spikes": i.volume_spikes});
 parent.append(el("h3", "Backtest · RSI / moving average"));
 const b = e.backtest;
 rows(parent, {"Closed trades": b.closed_trades, "Winning trades": b.winning_trades, "Losing trades": b.losing_trades, "Win rate (%)": b.win_rate_pct, "Average closed-trade return (%)": b.average_closed_trade_return_pct, "Asset drawdown (%) — not strategy equity": b.asset_max_drawdown_pct, "Open position": b.open_position});
 if (e.portfolio.included) { parent.append(el("h3", "Selected-coin position")); rows(parent, e.portfolio); }
 parent.append(el("h3", "Limitations")); const list = el("ul"); e.limitations.forEach(t => list.append(el("li", t))); parent.append(list);
 const details = el("details"); details.append(el("summary", "Exact evidence JSON"), el("pre", JSON.stringify(e, null, 2))); parent.append(details);
}
function selection(position) {
 if (!$("analysis-form").reportValidity()) return null;
 const body = {coin_id: $("coin").value, days: Number($("days").value)};
 if (!Number.isInteger(body.days)) return null;
 if (position && $("include-position").checked) {
  const amount = Number($("amount").value), cost = Number($("cost").value);
  if (!$("amount").value.trim() || !$("cost").value.trim() || !Number.isFinite(amount) || !Number.isFinite(cost) || amount < 0 || cost < 0) { status("Enter a finite, nonnegative amount and buy price."); return null; }
  body.selected_position = {amount, avg_buy_price: cost};
 }
 return body;
}
async function request(url, options) {
 let response;
 try { response = await fetch(url, options); }
 catch { throw new Error("Could not connect to the local server."); }
 let body; try { body = await response.json(); } catch { throw new Error("The server returned an invalid response."); }
 if (!response.ok) {
  const messages = {403: "Request origin is not allowed. Open the configured local address.", 422: "Check the coin, days, and position fields.", 429: "Server is busy. Try again later.", 502: "Market data is unavailable or invalid.", 503: "History is insufficient or stale.", 500: "An unexpected server error occurred."};
  const error = new Error(messages[response.status] || "Request failed.");
  if (body && body.coverage && typeof body.coverage === "object") error.coverage = body.coverage;
  throw error;
 }
 return body;
}
function showError(panel, error) { panel.append(el("p", "Request could not be completed. " + (error.message || "Try again manually."))); if (error.coverage) coverage(panel, error.coverage); }
function invalidate() {
 revision++; analysisSequence++;
 reset($("analysis"), "Market analysis"); reset($("ai"), "AI assessment");
 status(pendingAI ? "Selection changed. Waiting for the previous AI request to finish; its result will be discarded." : "Selection changed. Run a new analysis or assessment.");
}
["coin", "days", "include-position", "amount", "cost"].forEach(id => $(id).addEventListener("input", invalidate));
$("analysis-form").addEventListener("submit", async event => {
 event.preventDefault(); const body = selection(false); if (!body) return;
 const seq = ++analysisSequence, rev = revision; const panel = $("analysis"); reset(panel, "Market analysis"); status("Loading market evidence…");
 try { const result = await request(`/v1/analysis/${encodeURIComponent(body.coin_id)}?days=${body.days}`); if (seq !== analysisSequence || rev !== revision) return; const fragment = document.createDocumentFragment(); evidence(fragment, result); panel.append(fragment); status("Analysis ready."); }
 catch (error) { if (seq === analysisSequence && rev === revision) { showError(panel, error); status("Analysis unavailable."); } }
});
$("recommend").addEventListener("click", async () => {
 if (pendingAI) return; const body = selection(true); if (!body) return;
 pendingAI = true; $("recommend").disabled = true; const rev = revision, panel = $("ai"); reset(panel, "AI assessment"); status("Requesting AI assessment. This can take a minute…");
 try {
  const result = await request("/v1/recommendations", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (rev !== revision) return;
  if (!validEvidence(result.evidence) || !["completed", "unavailable"].includes(result.recommendation_status)) throw new Error("Invalid response");
  const fragment = document.createDocumentFragment();
  if (result.recommendation_status === "unavailable") {
   const message = result.ai_error?.message;
   fragment.append(el("p", typeof message === "string" && message.trim() ? message : "AI is unavailable or unconfigured. Raw evidence is available below."));
  }
  else {
   const r = result.recommendation;
   if (!r || !["BUY", "HOLD", "SELL"].includes(r.action) || !["low", "medium", "high"].includes(r.confidence) || !Array.isArray(r.reasons) || !Array.isArray(r.risks)) throw new Error("Invalid response");
   const action = el("p", r.action); action.className = "decision"; fragment.append(action, el("p", `${r.confidence} confidence · model judgment, not a probability`), el("p", r.confidence_explanation), el("p", r.summary), el("p", `Model: ${format(result.model)}`));
   for (const [title, entries] of [["Reasons", r.reasons], ["Risks", r.risks]]) {
    fragment.append(el("h3", title));
    for (const entry of entries) { if (!Array.isArray(entry.evidence_keys)) throw new Error("Invalid response"); fragment.append(el("p", entry.explanation)); const values = {};
     for (const key of entry.evidence_keys) { if (typeof key !== "string" || resolve(result.evidence, key) === undefined) throw new Error("Invalid citation"); values[key] = resolve(result.evidence, key); }
     rows(fragment, values);
    }
   }
  }
  fragment.append(el("h3", "Evidence used for this assessment")); evidence(fragment, result.evidence); panel.append(fragment); status(result.recommendation_status === "completed" ? "AI assessment ready." : "AI unavailable; evidence retained.");
 } catch (error) { if (rev === revision) { showError(panel, error); status("AI request failed. No automatic retry was made."); } }
 finally { pendingAI = false; $("recommend").disabled = false; if (rev !== revision) status("Previous AI request finished. You can request an assessment for the current selection."); }
});
