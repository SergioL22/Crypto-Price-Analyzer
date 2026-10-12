"use strict";
(() => {
 const kind = $("stock-kind"), search = $("stock-search"), select = $("stock-options");
 const status = $("stock-status"), result = $("stock-results"), load = $("stock-load"), run = $("stock-run"), days = $("stock-days");
 let assets = [], revision = 0, busy = false;
 const requested = typeof URLSearchParams !== "undefined" && window.location ? new URLSearchParams(window.location.search).get("asset") : null;
 const filterToggle = $("filter-toggle"), filterPanel = $("stock-filters");
 filterToggle?.addEventListener("click", () => {
  const open = !filterToggle._filterOpen;
  filterToggle._filterOpen = open;
  filterToggle.setAttribute("aria-expanded", String(open));
  filterPanel.hidden = !open;
 });
 document.addEventListener?.("keydown", event => { if (event.key === "Escape" && filterPanel && !filterPanel.hidden) { filterPanel.hidden = true; filterToggle._filterOpen = false; filterToggle.setAttribute("aria-expanded", "false"); filterToggle.focus?.(); } });
 if(requested?.startsWith("twelvedata:etf:")) kind.value="etf";
 function invalidate() { revision++; result.replaceChildren(); status.textContent = "Selection changed. Run research to see this listing’s data."; }
 function filter() {
  const previous = select.value, term = search.value.trim().toLowerCase();
  const matched = assets.filter(a => `${a.symbol} ${a.name} ${a.exchange}`.toLowerCase().includes(term) && (!$("stock-exchange")?.value || a.exchange === $("stock-exchange").value));
  select.replaceChildren();
  const placeholder = el("option", matched.length ? "Choose a company or fund" : assets.length ? "No matching companies or funds" : "Load the list to browse");
  placeholder.value = ""; placeholder.disabled = true; select.append(placeholder);
  for (const a of matched) { const option = el("option", `${a.name} (${a.symbol}) · ${a.exchange} · ${a.currency}`); option.value = a.id; select.append(option); }
  select.value = matched.some(a => a.id === previous) ? previous : "";
  $("stock-matches").textContent = assets.length ? `${matched.length} of ${assets.length} supported listings. All matches are available in the dropdown, sorted by name.` : "Load the company / fund list to browse by name.";
  run.disabled = busy || !select.value;
 }
 kind.addEventListener("change", () => { assets = []; invalidate(); filter(); });
 $("stock-exchange")?.addEventListener("change", () => { invalidate(); filter(); });
 $("stock-period")?.addEventListener("change", () => {
  const period = $("stock-period").value;
  const parts = new Intl.DateTimeFormat("en-US", {timeZone:"America/New_York",year:"numeric",month:"numeric",day:"numeric"}).formatToParts(new Date());
  const part = type => Number(parts.find(p=>p.type===type).value);
  days.value = period === "ytd" ? String(Math.floor((Date.UTC(part("year"),part("month")-1,part("day"))-Date.UTC(part("year"),0,1))/86400000)+1) : period;
  invalidate();
 });
 search.addEventListener("input", () => { invalidate(); filter(); });
 select.addEventListener("change", () => { invalidate(); run.disabled = busy || !select.value; }); days.addEventListener("input", invalidate);
 load.addEventListener("click", async () => {
  if (busy) return;
  invalidate(); const current = revision; busy = true; load.disabled = true; run.disabled = true;
  status.textContent = "Loading supported listings…";
  try {
   const data = await request(`/v1/assets?asset_class=${encodeURIComponent(kind.value)}`);
   if (current !== revision) return;
   assets = [...data.assets].sort((a,b) => a.name.localeCompare(b.name) || a.symbol.localeCompare(b.symbol) || a.exchange.localeCompare(b.exchange)); filter();
   if(requested && assets.some(a=>a.id===requested) && !search.value && !$("stock-exchange")?.value) select.value=requested;
   status.textContent = `${assets.length} listings loaded${data.stale ? " from an older cached catalog" : ""}. Availability depends on your provider account.`;
  } catch (error) { if (current === revision) status.textContent = error.message; }
  finally { busy = false; load.disabled = false; filter(); }
 });
 $("stock-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy || !select.value || !$("stock-form").reportValidity()) return;
  const current = ++revision; busy = true; load.disabled = true; run.disabled = true; result.replaceChildren(); status.textContent = "Loading completed trading sessions…";
  try {
   const data = await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(select.value)}&days=${encodeURIComponent(days.value)}`);
   if (current !== revision) return;
   result.append(el("h3", `${data.asset.name} (${data.asset.symbol}) · ${data.asset.exchange}`));
   const w = data.window;
   const notes=el("details");notes.append(el("summary","Data coverage and research limitations"),el("p", `${w.observations} of ${w.expected_sessions} completed sessions · ${w.start} to ${w.end} · USD · split-adjusted prices`));
   if(w.missing_sessions.length) result.append(el("p", "Some requested trading days are missing. The chart shows available data; indicators may be unavailable. Expand data coverage below for details."));
   if(data.history.length) {
    const first=data.history[0],last=data.history.at(-1),cards=el("div");cards.className="summary-cards";
    const price=el("article"),change=el("article");
    price.className="price-hero";
    const priceValue=el("p",priceLabel(last.price));priceValue.className="price-value";
    price.append(el("h3","Latest available close"),priceValue,el("p",`${last.date} · USD · historical close`));
    change.append(el("h3","Price change in returned history"),el("p",`${((last.price/first.price-1)*100).toFixed(2)}% · ${first.date} to ${last.date}. Excludes dividends.`));
    cards.append(price,change);result.append(cards);
   }
   priceChart(result, data.history, {sessions: true});
   if (data.indicators) {
    const i = data.indicators;
    const signals = el("div"); signals.className = "signal-cards";
    const addSignal = (title, text) => { const card=el("article"); card.append(el("h3",title),el("p",text)); signals.append(card); };
    const latest = data.history.at(-1)?.price;
    addSignal("Price trend", Number.isFinite(i.ma_25) && Number.isFinite(latest)
     ? `The latest close is ${latest > i.ma_25 ? "above" : latest < i.ma_25 ? "below" : "at"} its 25-session average. This describes recent price direction, not a forecast.`
     : "There is not enough data to describe the recent trend.");
    addSignal("Recent momentum", Number.isFinite(i.rsi_14)
     ? `${i.rsi_14 > 70 ? "Recent gains have been strong" : i.rsi_14 < 30 ? "Recent losses have been strong" : "RSI is between its usual extreme thresholds"} (RSI ${format(i.rsi_14)} / 100). This does not predict a reversal.`
     : "RSI is unavailable for this window.");
    addSignal("Momentum signal", Number.isFinite(i.macd_histogram)
     ? `MACD is ${i.macd_histogram > 0 ? "above" : i.macd_histogram < 0 ? "below" : "at"} its signal line. This compares two smoothed price trends; it is not a buy or sell instruction.`
     : "MACD is unavailable for this window.");
    result.append(el("h3", "What the signals mean"), signals);
    const details = el("details"), table = el("table"); details.append(el("summary", "Exact indicator values"));
    for (const [key, value] of Object.entries(i)) { const row = el("tr"); row.append(el("th", key.replaceAll("_", " ")), el("td", format(value))); table.append(row); }
    details.append(table); result.append(details);
   } else result.append(el("p", "Indicators unavailable: at least 35 observations and complete session coverage are required. Try a longer window or retry later if the latest bar is delayed."));
   if (data.history.length) notes.append(el("p", `Returned history: ${data.history[0].date} to ${data.history.at(-1).date}. The first returned date is not a verified listing date.`));
   if (w.missing_sessions.length) {
    const gaps = el("details"); gaps.append(el("summary", `${w.missing_sessions.length} requested sessions unavailable`), el("p", w.missing_sessions.join(", ")));
    notes.append(gaps);
   }
   for (const text of data.limitations) notes.append(el("p", text));
   result.append(notes);
   status.textContent = "Stock research loaded. No OpenAI request was made.";
  } catch (error) { if (current === revision) status.textContent = error.message; }
  finally { busy = false; load.disabled = false; filter(); }
 });
 filter();
})();
