"use strict";
(() => {
 const kind = $("stock-kind"), search = $("stock-search"), select = $("stock-options");
 const status = $("stock-status"), result = $("stock-results"), load = $("stock-load"), run = $("stock-run"), days = $("stock-days");
 let optionLimit=200,filterKey='',searchTimer=null;
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
 if(requested?.startsWith(demoWorkspace()?"demo:etf:":"twelvedata:etf:")) kind.value="etf";
 function invalidate() { revision++; result.replaceChildren(); if($("stock-empty"))$("stock-empty").hidden=false; status.setAttribute("data-state","idle");status.textContent = ""; }
 function renderListing(){
  const root=$('stock-listing-summary');if(!root)return;const asset=assets.find(a=>a.id===select.value);if(asset&&root._listingId===asset.id)return;root._listingId=asset?.id||null;root.replaceChildren();root.hidden=!asset;if(!asset)return;
  const info=ListingDiscovery.describe(asset);root.append(el('summary','About this listing'),el('span',info.type),el('p',info.text));companyProfilePanel(root,asset,()=>request(`/v1/company-profile?asset_id=${encodeURIComponent(asset.id)}`),()=>root._listingId===asset.id&&select.value===asset.id);
 }
 function updateExchangeCounts(){const exchange=$('stock-exchange');if(!exchange)return;for(const option of Array.from(exchange.children)){option._catalogLabel??=option.textContent;const count=option.value?assets.filter(a=>a.exchange===option.value).length:assets.length;option.textContent=`${option._catalogLabel} (${count})`;}}
 function filter() {
  const previous = select.value, term = search.value.trim().toLowerCase();
  const exact=$("stock-query-mode")?.value==='ticker',order=$("stock-sort")?.value||'name';
  const matched = ListingDiscovery.sort(assets.filter(a=>ListingDiscovery.matches(a,{query:search.value,exact,exchange:$('stock-exchange')?.value,initial:$('stock-initial')?.value})),order,search.value);
  const key=JSON.stringify([search.value,exact,order,$('stock-exchange')?.value,$('stock-initial')?.value,kind.value]);if(key!==filterKey){filterKey=key;optionLimit=200;}
  const shown=matched.slice(0,optionLimit);if(previous&&!shown.some(a=>a.id===previous)){const selected=matched.find(a=>a.id===previous);if(selected)shown.push(selected);}
  select.replaceChildren();
  const placeholder = el("option", matched.length ? "Choose a company or fund" : assets.length ? "No matching companies or funds" : "Load the list to browse");
  placeholder.value = ""; placeholder.disabled = true; select.append(placeholder);
  for (const a of shown) { const option = el("option", `${a.name} (${a.symbol}) · ${a.exchange} · ${a.currency}`); option.value = a.id; select.append(option); }
  select.value = matched.some(a => a.id === previous) ? previous : "";
  $("stock-matches").textContent = assets.length ? `${matched.length} of ${assets.length} listings${matched.length>optionLimit?` · showing ${shown.length}; refine your search or load more`:""}` : "Load the company / fund list to browse by name.";
  if($('stock-more')){$('stock-more').hidden=matched.length<=optionLimit;$('stock-more').textContent=`Show next ${Math.min(200,Math.max(0,matched.length-optionLimit))} matches`;}
  select.disabled=false;renderListing();
  run.disabled = busy || !select.value;run.hidden=!select.value;
  if($("equity-save")){$("equity-save").disabled=busy||!select.value;$("equity-save").hidden=!select.value;}
 }
 kind.addEventListener("change", () => { assets = []; if($('stock-exchange'))$('stock-exchange').value=''; updateExchangeCounts(); invalidate(); filter(); pendingCatalog = true; if (!busy) loadCatalog(); });
 $("stock-exchange")?.addEventListener("change", () => { invalidate(); filter(); });
 for(const id of ['stock-query-mode','stock-sort','stock-initial'])$(id)?.addEventListener('change',()=>{invalidate();filter();});
 $('stock-reset-filters')?.addEventListener('click',()=>{search.value='';for(const [id,value]of [['stock-exchange',''],['stock-query-mode','contains'],['stock-sort','relevance'],['stock-initial','']])if($(id))$(id).value=value;invalidate();filter();});
 $("stock-period")?.addEventListener("change", () => {
  const period = $("stock-period").value;
  const parts = new Intl.DateTimeFormat("en-US", {timeZone:"America/New_York",year:"numeric",month:"numeric",day:"numeric"}).formatToParts(new Date());
  const part = type => Number(parts.find(p=>p.type===type).value);
  days.value = period === "ytd" ? String(Math.floor((Date.UTC(part("year"),part("month")-1,part("day"))-Date.UTC(part("year"),0,1))/86400000)+1) : period;
  invalidate(); pendingAnalysis=true;if(!busy)return analyze();
 });
 $('stock-more')?.addEventListener('click',()=>{optionLimit+=200;filter();});
 search.addEventListener("input", () => { invalidate();select.disabled=true;run.disabled=true;if($('equity-save'))$('equity-save').disabled=true;if(typeof setTimeout==='function'&&typeof clearTimeout==='function'){if(searchTimer!==null)clearTimeout(searchTimer);searchTimer=setTimeout(()=>{searchTimer=null;filter();},120);}else filter(); });
 select.addEventListener("change", () => { invalidate(); renderListing(); run.disabled = busy || !select.value;if($("equity-save"))$("equity-save").disabled=busy||!select.value; pendingAnalysis=true;if(!busy) return analyze(); }); days.addEventListener("input", invalidate); days.addEventListener("change",()=>{pendingAnalysis=true;if(!busy)return analyze();});
 async function loadCatalog() {
  if (busy) return;
  pendingCatalog = false; if($("stock-retry"))$("stock-retry").hidden=true;
  invalidate(); const current = revision, catalogKind=kind.value; busy = true; load.disabled = true; run.disabled = true;
  load.textContent="Loading listings…";load.setAttribute("aria-busy","true");status.setAttribute("data-state","loading");status.textContent = "Loading companies and funds...";
  try {
   const data = await request(`/v1/assets?asset_class=${encodeURIComponent(kind.value)}`);
   if (catalogKind !== kind.value) return;
   assets = ListingDiscovery.sort(data.assets,'name'); updateExchangeCounts(); filter();
   if(requested && assets.some(a=>a.id===requested) && !search.value && !$("stock-exchange")?.value) {if(!Array.from(select.children).some(o=>o.value===requested)){const a=assets.find(a=>a.id===requested),option=el("option",`${a.name} (${a.symbol}) · ${a.exchange} · ${a.currency}`);option.value=a.id;select.append(option);}select.value=requested;pendingAnalysis=true;}
   status.setAttribute("data-state","idle");status.textContent = data.stale?"Showing a cached list. Reload it from Filters if needed.":assets.length?"":"No supported listings are available.";
  } catch (error) { if (catalogKind === kind.value) {if($("stock-retry"))$("stock-retry").hidden=false;status.setAttribute("data-state","error");status.textContent = error.message;} }
  finally { busy = false; load.disabled = false;load.textContent=assets.length ? "Reload listings" : "Retry loading listings";load.setAttribute("aria-busy","false"); filter(); if(pendingCatalog) loadCatalog();else if(pendingAnalysis) analyze(); }
 }
 load.addEventListener("click", loadCatalog); $("stock-retry")?.addEventListener("click",loadCatalog);
 async function analyze(event) {
  event?.preventDefault(); pendingAnalysis=false; if(document.body?.dataset?.view==="compare")return; if (busy || !select.value || !$("stock-form").reportValidity()) return;
  const current = ++revision; if($("stock-empty"))$("stock-empty").hidden=true; busy = true; load.disabled = true; run.disabled = true;run.textContent="Loading analysis…";result.setAttribute("aria-busy","true"); result.replaceChildren(); status.setAttribute("data-state","loading");status.textContent = "Loading price history...";
  try {
   const data = await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(select.value)}&days=${encodeURIComponent(days.value)}${$('stock-refresh')?.checked?'&refresh=true':''}`);
   if (current !== revision) return;
   const resultHeading=el("div");resultHeading.className="result-heading";const changeListing=el("a","Change listing");changeListing.href="#stock-search";resultHeading.append(el("h3", `${data.asset.name} (${data.asset.symbol}) · ${data.asset.exchange}`),changeListing);result.append(resultHeading);
   const w = data.window;

   const notes=el("details");notes.append(el("summary","Data coverage and research limitations"));if(data.history_source)notes.append(el('p',data.history_source.cache_hit?'Recent history reused; no new provider history request.':'History fetched for this request.'));notes.append(el("p", `${w.observations} of ${w.expected_sessions} completed sessions · ${w.start} to ${w.end} · USD · ${demoWorkspace()?"synthetic generated prices":"split-adjusted prices"}`));
   if(data.history_source)notes.append(el('p',`Original history fetch: ${data.history_source.fetched_at_utc} · ${data.history_source.age_seconds}s old when requested. Cache reuse never means a live quote.`));
   if(w.missing_sessions.length) result.append(el("p", "Some requested trading days are missing. The chart shows available data; indicators may be unavailable. Expand data coverage below for details."));
   if(data.history.length) {
    const first=data.history[0],last=data.history.at(-1),cards=el("div");cards.className="summary-cards";
    const price=el("article"),change=el("article");
    price.className="price-hero";
    const priceValue=el("p",priceLabel(last.price));priceValue.className="price-value";
    price.append(el("h3",demoWorkspace()?"Synthetic demo close":"Latest available close"),priceValue,el("p",`${last.date} · USD · historical close`));
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
    const signalDetails=el("details");signalDetails.className="signal-details";signalDetails.append(el("summary","Understand the indicators"),signals);result.append(signalDetails);
    const details = el("details"), table = el("table"); details.className="chart-table";details.append(el("summary", "Exact indicator values"));
    table.className="indicator-table";table.append(el("caption", `Latest loaded session: ${data.history.at(-1)?.date || "Unavailable"}. Calculated over the original history; zoom does not recalculate these values.`));
    const head=el("tr");for(const text of ["Indicator","Value","Meaning / units"]){const th=el("th",text);th.setAttribute("scope","col");head.append(th);}table.append(head);
    const descriptions={rsi_14:["RSI (14)","Wilder-smoothed momentum on a 0–100 scale. Conventional thresholds: 30 and 70; neither guarantees a reversal."],ma_7:["Moving average (7)","Mean close over 7 trading observations, in USD."],ma_25:["Moving average (25)","Mean close over 25 trading observations, in USD."],macd:["MACD","12-observation EMA minus 26-observation EMA, in USD."],macd_signal:["MACD signal","9-observation EMA of MACD, in USD."],macd_histogram:["MACD histogram","MACD minus its signal line, in USD; not a probability."],bollinger_lower:["Bollinger lower","20-observation average minus two standard deviations, in USD."],bollinger_middle:["Bollinger middle","20-observation average close, in USD."],bollinger_upper:["Bollinger upper","20-observation average plus two standard deviations, in USD."]};
    for (const [key, value] of Object.entries(i)) { const row = el("tr"),[label,meaning]=descriptions[key]||[key.replaceAll("_", " "),"Provider / analysis value"];const th=el("th",label);th.setAttribute("scope","row");row.append(th, el("td", value===null?"Unavailable":format(value)),el("td",meaning)); table.append(row); }
    details.append(table); signalDetails.append(details);
   } else result.append(el("p", "Indicators unavailable: at least 35 observations and complete session coverage are required. Try a longer window or retry later if the latest bar is delayed."));
   if (data.history.length) notes.append(el("p", `Returned history: ${data.history[0].date} to ${data.history.at(-1).date}. The first returned date is not a verified listing date.`));
   if (w.missing_sessions.length) {
    const gaps = el("details"); gaps.append(el("summary", `${w.missing_sessions.length} requested sessions unavailable`), el("p", w.missing_sessions.join(", ")));
    notes.append(gaps);
   }
   for (const text of data.limitations) notes.append(el("p", text));
   result.append(notes);
   if($("stock-empty"))$("stock-empty").hidden=true;
   status.setAttribute("data-state","success");status.textContent = "Analysis ready.";result.scrollIntoView?.({behavior:window.matchMedia?.("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
  } catch (error) { if (current === revision) {status.setAttribute("data-state","error");status.textContent = error.message;} }
  finally { busy = false; load.disabled = false;run.textContent="Update analysis";result.setAttribute("aria-busy","false"); filter(); if(pendingCatalog) loadCatalog();else if(pendingAnalysis) analyze(); }
 }
 $("stock-form").addEventListener("submit", analyze);
 filter();
 document.addEventListener?.("DOMContentLoaded", loadCatalog, {once:true});
})();
