"use strict";
(() => {
 const kind = $("stock-kind"), search = $("stock-search"), select = $("stock-options");
 const status = $("stock-status"), result = $("stock-results"), load = $("stock-load"), run = $("stock-run"), days = $("stock-days");
 let assets = [], revision = 0, busy = false, pendingCatalog = false, pendingAnalysis = false;
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
 function invalidate() { revision++; result.replaceChildren(); if($("stock-empty"))$("stock-empty").hidden=false; status.textContent = "Choose your listing and time range, then view its analysis."; }
 function filter() {
  const previous = select.value, term = search.value.trim().toLowerCase();
  const exact=$("stock-query-mode")?.value==='ticker',order=$("stock-sort")?.value||'name';
  const matched = assets.filter(a => (!term||(exact?a.symbol.toLowerCase()===term:`${a.symbol} ${a.name} ${a.exchange}`.toLowerCase().includes(term))) && (!$("stock-exchange")?.value || a.exchange === $("stock-exchange").value));
  matched.sort((a,b)=>String(a[order]||a.name).localeCompare(String(b[order]||b.name))||a.name.localeCompare(b.name)||a.exchange.localeCompare(b.exchange));
  select.replaceChildren();
  const placeholder = el("option", matched.length ? "Choose a company or fund" : assets.length ? "No matching companies or funds" : "Load the list to browse");
  placeholder.value = ""; placeholder.disabled = true; select.append(placeholder);
  for (const a of matched) { const option = el("option", `${a.name} (${a.symbol}) · ${a.exchange} · ${a.currency}`); option.value = a.id; select.append(option); }
  select.value = matched.some(a => a.id === previous) ? previous : "";
  $("stock-matches").textContent = assets.length ? `${matched.length} of ${assets.length} supported listings. All matches are available in the dropdown, sorted by ${order}.` : "Load the company / fund list to browse by name.";
  run.disabled = busy || !select.value;
  if($("equity-save"))$("equity-save").disabled=busy||!select.value;
 }
 kind.addEventListener("change", () => { assets = []; invalidate(); filter(); pendingCatalog = true; if (!busy) loadCatalog(); });
 $("stock-exchange")?.addEventListener("change", () => { invalidate(); filter(); });
 for(const id of ['stock-query-mode','stock-sort'])$(id)?.addEventListener('change',()=>{invalidate();filter();});
 $('stock-reset-filters')?.addEventListener('click',()=>{search.value='';for(const [id,value]of [['stock-exchange',''],['stock-query-mode','contains'],['stock-sort','name']])if($(id))$(id).value=value;invalidate();filter();});
 $("stock-period")?.addEventListener("change", () => {
  const period = $("stock-period").value;
  const parts = new Intl.DateTimeFormat("en-US", {timeZone:"America/New_York",year:"numeric",month:"numeric",day:"numeric"}).formatToParts(new Date());
  const part = type => Number(parts.find(p=>p.type===type).value);
  days.value = period === "ytd" ? String(Math.floor((Date.UTC(part("year"),part("month")-1,part("day"))-Date.UTC(part("year"),0,1))/86400000)+1) : period;
  invalidate();
 });
 search.addEventListener("input", () => { invalidate(); filter(); });
 select.addEventListener("change", () => { invalidate(); run.disabled = busy || !select.value;if($("equity-save"))$("equity-save").disabled=busy||!select.value; pendingAnalysis=true;if(!busy) return analyze(); }); days.addEventListener("input", invalidate);
 async function loadCatalog() {
  if (busy) return;
  pendingCatalog = false;
  invalidate(); const current = revision, catalogKind=kind.value; busy = true; load.disabled = true; run.disabled = true;
  load.textContent="Loading listings…";load.setAttribute("aria-busy","true");status.textContent = "Loading supported listings…";
  try {
   const data = await request(`/v1/assets?asset_class=${encodeURIComponent(kind.value)}`);
   if (catalogKind !== kind.value) return;
   assets = [...data.assets].sort((a,b) => a.name.localeCompare(b.name) || a.symbol.localeCompare(b.symbol) || a.exchange.localeCompare(b.exchange)); filter();
   if(requested && assets.some(a=>a.id===requested) && !search.value && !$("stock-exchange")?.value) {select.value=requested;pendingAnalysis=true;}
   status.textContent = `${assets.length} listings loaded${data.stale ? " from an older cached catalog" : ""}. Availability depends on your provider account.`;
  } catch (error) { if (catalogKind === kind.value) status.textContent = error.message; }
  finally { busy = false; load.disabled = false;load.textContent=assets.length ? "Reload listings" : "Retry loading listings";load.setAttribute("aria-busy","false"); filter(); if(pendingCatalog) loadCatalog();else if(pendingAnalysis) analyze(); }
 }
 load.addEventListener("click", loadCatalog);
 async function analyze(event) {
  event?.preventDefault(); pendingAnalysis=false; if (busy || !select.value || !$("stock-form").reportValidity()) return;
  const current = ++revision; busy = true; load.disabled = true; run.disabled = true;run.textContent="Loading analysis…";result.setAttribute("aria-busy","true"); result.replaceChildren(); status.textContent = "Loading completed trading sessions…";
  try {
   const data = await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(select.value)}&days=${encodeURIComponent(days.value)}${$('stock-refresh')?.checked?'&refresh=true':''}`);
   if (current !== revision) return;
   result.append(el("h3", `${data.asset.name} (${data.asset.symbol}) · ${data.asset.exchange}`));
   const w = data.window;
   if(data.history_source)result.append(el('p',data.history_source.cache_hit?'Recent history reused; no new provider history request.':'History fetched for this request.'));
   const notes=el("details");notes.append(el("summary","Data coverage and research limitations"),el("p", `${w.observations} of ${w.expected_sessions} completed sessions · ${w.start} to ${w.end} · USD · split-adjusted prices`));
   if(data.history_source)notes.append(el('p',`Original history fetch: ${data.history_source.fetched_at_utc} · ${data.history_source.age_seconds}s old when requested. Cache reuse never means a live quote.`));
   if(w.missing_sessions.length) result.append(el("p", "Some requested trading days are missing. The chart shows available data; indicators may be unavailable. Expand data coverage below for details."));
   if(data.history.length) {
    const first=data.history[0],last=data.history.at(-1),cards=el("div");cards.className="summary-cards";
    const price=el("article"),change=el("article");
    price.className="price-hero";
    const priceValue=el("p",priceLabel(last.price));priceValue.className="price-value";
    price.append(el("h3","Latest available close"),priceValue,el("p",`${last.date} · USD · historical close`));
    const percent=(last.price/first.price-1)*100,returnValue=el("p",`${percent>0?'+':''}${percent.toFixed(2)}%`);returnValue.className=`return-value ${percent>0?'return-positive':percent<0?'return-negative':'return-flat'}`;
    change.append(el("h3","Price change in returned history"),returnValue,el("p",`${first.date} to ${last.date} · excludes dividends`));
    cards.append(price,change);result.append(cards);
   }
   priceChart(result, data.history, {sessions: true, bars: data.bars});
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
    const details = el("details"), table = el("table"); details.className="chart-table";details.append(el("summary", "Exact indicator values"));
    table.className="indicator-table";table.append(el("caption", `Latest loaded session: ${data.history.at(-1)?.date || "Unavailable"}. Calculated over the original history; zoom does not recalculate these values.`));
    const head=el("tr");for(const text of ["Indicator","Value","Meaning / units"]){const th=el("th",text);th.setAttribute("scope","col");head.append(th);}table.append(head);
    const descriptions={rsi_14:["RSI (14)","Wilder-smoothed momentum on a 0–100 scale. Conventional thresholds: 30 and 70; neither guarantees a reversal."],ma_7:["Moving average (7)","Mean close over 7 trading observations, in USD."],ma_25:["Moving average (25)","Mean close over 25 trading observations, in USD."],macd:["MACD","12-observation EMA minus 26-observation EMA, in USD."],macd_signal:["MACD signal","9-observation EMA of MACD, in USD."],macd_histogram:["MACD histogram","MACD minus its signal line, in USD; not a probability."],bollinger_lower:["Bollinger lower","20-observation average minus two standard deviations, in USD."],bollinger_middle:["Bollinger middle","20-observation average close, in USD."],bollinger_upper:["Bollinger upper","20-observation average plus two standard deviations, in USD."]};
    for (const [key, value] of Object.entries(i)) { const row = el("tr"),[label,meaning]=descriptions[key]||[key.replaceAll("_", " "),"Provider / analysis value"];const th=el("th",label);th.setAttribute("scope","row");row.append(th, el("td", value===null?"Unavailable":format(value)),el("td",meaning)); table.append(row); }
    details.append(table); result.append(details);
   } else result.append(el("p", "Indicators unavailable: at least 35 observations and complete session coverage are required. Try a longer window or retry later if the latest bar is delayed."));
   if (data.history.length) notes.append(el("p", `Returned history: ${data.history[0].date} to ${data.history.at(-1).date}. The first returned date is not a verified listing date.`));
   if (w.missing_sessions.length) {
    const gaps = el("details"); gaps.append(el("summary", `${w.missing_sessions.length} requested sessions unavailable`), el("p", w.missing_sessions.join(", ")));
    notes.append(gaps);
   }
   for (const text of data.limitations) notes.append(el("p", text));
   result.append(notes);
   if($("stock-empty"))$("stock-empty").hidden=true;
   status.textContent = `Analysis ready · latest available close ${data.history.at(-1)?.date || "unavailable"}. Historical prices, not a live quote.`;
  } catch (error) { if (current === revision) status.textContent = error.message; }
  finally { busy = false; load.disabled = false;run.textContent="Update analysis";result.setAttribute("aria-busy","false"); filter(); if(pendingCatalog) loadCatalog();else if(pendingAnalysis) analyze(); }
 }
 $("stock-form").addEventListener("submit", analyze);
 filter();
 document.addEventListener?.("DOMContentLoaded", loadCatalog, {once:true});
})();
