"use strict";
const resolve = (obj, key) => key.split(".").reduce((value, part) => value !== null && typeof value === "object" && Object.hasOwn(value, part) ? value[part] : undefined, obj);
const featuredCoins = [
 {id:"bitcoin",name:"Bitcoin",symbol:"BTC"},
 {id:"ethereum",name:"Ethereum",symbol:"ETH"},
 {id:"solana",name:"Solana",symbol:"SOL"},
 {id:"ripple",name:"XRP",symbol:"XRP"},
 {id:"dogecoin",name:"Dogecoin",symbol:"DOGE"},
 {id:"cardano",name:"Cardano",symbol:"ADA"},
 {id:"litecoin",name:"Litecoin",symbol:"LTC"},
 {id:"chainlink",name:"Chainlink",symbol:"LINK"}
];
let catalogCoins = featuredCoins;
let catalogPending = false;
const coinLabel = id => { const coin = catalogCoins.find(c => c.id === id) || featuredCoins.find(c => c.id === id); return coin ? `${coin.name} (${coin.symbol}) · ${coin.id}` : `${id} · custom CoinGecko ID`; };
let revision = 0, analysisSequence = 0, pendingAI = false;
function updateCoinLabel() { $("selected-coin").textContent = `Selected: ${coinLabel($("coin").value)}`; }
function chooseCoin(id) {
 if (!catalogCoins.some(c => c.id === id) && !featuredCoins.some(c => c.id === id)) return;
 $("coin").value = id;
 $("coin-options").value = id;
 invalidate();
}
function filterCoins() {
 const query = $("coin-search").value.trim().toLowerCase();
 const allMatches = catalogCoins.filter(c => `${c.name} ${c.symbol} ${c.id}`.toLowerCase().includes(query));
 const matches = allMatches.slice(0,100);
 $("coin-options").replaceChildren();
 const placeholder = el("option", matches.length ? "Choose a matching coin" : "No matching coins");
 placeholder.value = ""; placeholder.disabled = true;
 $("coin-options").append(placeholder);
 for (const coin of matches) { const option = el("option", coinLabel(coin.id)); option.value = coin.id; $("coin-options").append(option); }
 // Filtering never changes the selected market or starts a request.
 $("coin-options").value = matches.some(c => c.id === $("coin").value) ? $("coin").value : "";
 $("coin-options").disabled = matches.length === 0;
 $("coin-search-status").textContent = matches.length ? `${allMatches.length} matches; showing ${matches.length}. Refine your search or choose a coin.` : "No coins match the loaded list. Try a different name or enter a CoinGecko ID below.";
}
$("load-coins").addEventListener("click", async () => {
 if (catalogPending) return;
 catalogPending = true; $("load-coins").disabled = true;
 $("catalog-status").textContent = "Loading coin catalog…";
 try {
  const result = await request("/v1/coins");
  if (!Array.isArray(result.coins) || !result.coins.length || typeof result.stale !== "boolean" || typeof result.fetched_at_utc !== "string" || !result.coins.every(c => c && typeof c.id === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(c.id) && c.id.length <= 100 && typeof c.name === "string" && typeof c.symbol === "string")) throw new Error("Invalid catalog");
  catalogCoins = result.coins;
  $("catalog-status").textContent = `${result.coins.length} coins loaded · ${result.stale ? "Cached list; refresh unavailable" : "Catalog snapshot"} ${result.fetched_at_utc}. Listing does not guarantee available history.`;
  filterCoins(); updateCoinLabel();
 } catch {
  $("catalog-status").textContent = "Could not load the catalog. Your current list and manual ID entry still work. Retry later.";
 } finally { catalogPending = false; $("load-coins").disabled = false; }
});
$("coin-search").addEventListener("input", filterCoins);
$("coin-options").addEventListener("change", () => chooseCoin($("coin-options").value));
for (const coin of featuredCoins.slice(0,3)) { const button = el("button", coin.name); button.type = "button"; button.addEventListener("click", () => { $("coin-search").value = ""; filterCoins(); chooseCoin(coin.id); }); $("coin-quick").append(button); }
filterCoins();
updateCoinLabel();
function status(text) { $("status").textContent = text; }
function reset(panel, title) { panel.replaceChildren(el("h2", title)); }
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
 parent.append(el("h3", coinLabel(e.coin_id)));
 const priceHero=el("article");priceHero.className="price-hero";
 const priceValue=el("p",priceLabel(e.indicators.latest_history_price_usd));priceValue.className="price-value";
 priceHero.append(el("h3","Latest historical price"),priceValue,el("p","USD · historical observation, not a live quote"));parent.append(priceHero);
 if (e.history) priceChart(parent, e.history);
 visualSummary(parent, e);
 const technical = el("details"); technical.append(el("summary", "Technical details and limitations")); parent.append(technical); parent = technical;
 parent.append(el("p", `Snapshot ${e.generated_at_utc}`));
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
function showError(panel, error) { panel.append(el("p", "Request could not be completed. " + (error.message || "Try again manually."))); if (error.coverage) coverage(panel, error.coverage); }
function invalidate() {
 updateCoinLabel();
 filterCoins();
 revision++; analysisSequence++;
 reset($("analysis"), "Market analysis"); reset($("ai"), "AI assessment");
 status(pendingAI ? "Selection changed. Waiting for the previous AI request to finish; its result will be discarded." : "Selection changed. Run a new analysis or assessment.");
}
["coin", "days", "include-position", "amount", "cost"].forEach(id => $(id).addEventListener("input", invalidate));
$("analysis-form").addEventListener("submit", async event => {
 event.preventDefault(); const body = selection(false); if (!body) return;
 const seq = ++analysisSequence, rev = revision; const panel = $("analysis"); reset(panel, "Market analysis"); status("Loading market evidence…");
 try { const result = await request(`/v1/analysis/${encodeURIComponent(body.coin_id)}?days=${body.days}&include_history=true`); if (seq !== analysisSequence || rev !== revision) return; const fragment = document.createDocumentFragment(); evidence(fragment, result); panel.append(fragment); status("Analysis ready."); }
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

if (typeof window !== "undefined" && window.location) {
 const requestedCoin = new URLSearchParams(window.location.search).get("coin");
 if (requestedCoin && requestedCoin.length <= 100 && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requestedCoin)) { $("coin").value = requestedCoin; invalidate(); }
}
