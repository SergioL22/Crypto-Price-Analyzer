"use strict";
// Separate browser-local stock workspace; legacy crypto files are never rewritten.
(() => {
 const key = "research-desk.equities.v1";
 const valid = id => typeof id === "string" && /^twelvedata:(stock|etf):(XNYS|XNAS|XNGS|XNMS|XNCM|ARCX|XASE|BATS):USD:[A-Za-z0-9.^_-]{1,100}$/.test(id);
 const empty = () => ({version:1, listings:[], holdings:[], alerts:[]});
 function read() {
  const raw = localStorage.getItem(key); if (raw === null) return empty();
  return validate(JSON.parse(raw));
 }
 function validate(data) {
  if (data.version !== 1 || !Array.isArray(data.listings) || !Array.isArray(data.holdings) || !Array.isArray(data.alerts) ||
      data.listings.length > 50 || data.holdings.length > 50 || data.alerts.length > 50 ||
      !data.listings.every(a=>valid(a.id) && typeof a.name === "string" && a.name.length <= 500) ||
      new Set(data.listings.map(a=>a.id)).size !== data.listings.length ||
      !data.holdings.every(h=>valid(h.id) && Number.isFinite(h.quantity) && h.quantity > 0 && Number.isFinite(h.cost) && h.cost >= 0) ||
      new Set(data.holdings.map(a=>a.id)).size !== data.holdings.length ||
      !data.alerts.every(a=>valid(a.id) && ["price","rsi"].includes(a.type) && ["above","below"].includes(a.direction) && Number.isFinite(a.threshold) && a.threshold >= 0 && (a.type !== "rsi" || a.threshold <= 100) && typeof a.triggered === "boolean")) throw new Error("Saved stock workspace is invalid; existing data has been preserved.");
  return {version:1,listings:data.listings.map(({id,name})=>({id,name})),holdings:data.holdings.map(({id,quantity,cost})=>({id,quantity,cost})),alerts:data.alerts.map(({id,type,direction,threshold,triggered})=>({id,type,direction,threshold,triggered}))};
 }
 function save(data) { localStorage.setItem(key, JSON.stringify(data)); }
 let restore=null;
 $("equity-export")?.addEventListener("click",()=>{
  try{const blob=new Blob([JSON.stringify(read(),null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),link=el("a");link.href=url;link.download="stock-workspace-backup.json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);say("Stock workspace backup downloaded. Keep holdings private.");}catch{say("Could not export the stock workspace.");}
 });
 $("equity-restore-file")?.addEventListener("change",()=>{restore=null;$("equity-restore-apply").disabled=true;});
 $("equity-restore-preview")?.addEventListener("click",async()=>{
  restore=null;$("equity-restore-apply").disabled=true;
  const file=$("equity-restore-file").files[0];if(!file||file.size>500000){say("Choose a stock workspace JSON backup under 500 KB.");return;}
  try{const data=validate(JSON.parse(await file.text()));if($("equity-restore-file").files[0]!==file)return;
   restore={data,before:localStorage.getItem(key)};say(`Preview: ${data.listings.length} listings, ${data.holdings.length} holdings, ${data.alerts.length} alerts. Restore will replace this browser's complete stock workspace.`);$("equity-restore-apply").disabled=false;
  }catch{say("Invalid stock backup; nothing was changed.");}
 });
 $("equity-restore-apply")?.addEventListener("click",()=>{
  if(!restore||!window.confirm("Replace this browser's stock watchlist, holdings and alerts with the preview? Export your current workspace first if you need to keep it."))return;
  try{if(localStorage.getItem(key)!==restore.before)throw Error();save(restore.data);restore=null;$("equity-restore-apply").disabled=true;say("Stock workspace restored in this browser.");}catch{say("Workspace changed or storage is unavailable. Preview again before restoring.");}
 });
 const say = text => { const node = $("equity-status") || $("equity-save-status"); if(node) node.textContent=text; };
 function change(fn) { try { const data=read(); fn(data); save(data); render(); if(monitorStart){if(monitoring)stopMonitoring("Workspace changed. Restart monitoring to use the updated rules.");observations.clear();drawMonitoring();} $("equity-valuation")?.replaceChildren(); say("Stock workspace saved in this browser."); } catch { say("Could not save the stock workspace. Existing data was not intentionally replaced; check browser storage permissions."); } }
 function label(data,id) { return data.listings.find(a=>a.id===id)?.name || id; }
 function render() {
  const container=$("equity-list");
  if(!container) return;
  try {
   const data=read(); container.replaceChildren();
   for(const a of data.listings) {
    const row=el("li"), open=el("a",a.name), remove=el("button","Remove from watchlist");
    open.href=`/stocks.html?asset=${encodeURIComponent(a.id)}`;
    remove.type="button"; remove.addEventListener("click",()=>change(d=>{d.listings=d.listings.filter(x=>x.id!==a.id);}));
    row.append(open,remove);container.append(row);
   }
   if(!data.listings.length) {const item=el("li","Your watchlist is empty. "),link=el("a","Explore companies and funds");link.href="/";item.className="empty-state";item.append(link);container.append(item);}
   for(const selectId of ["equity-holding","equity-alert-listing"]) {
    const select=$(selectId);if(!select)continue;
    const previous=select.value;select.replaceChildren();
    const prompt=el("option","Choose a saved listing");prompt.value="";select.append(prompt);
    // Include holdings removed from the watchlist so they remain editable.
    const ids=[...new Set([...data.listings.map(a=>a.id),...data.holdings.map(h=>h.id),...data.alerts.map(a=>a.id)])];
    for(const id of ids){const option=el("option",label(data,id));option.value=id;select.append(option);}
    select.value=ids.includes(previous)?previous:"";
   }
   const holdings=$("equity-holdings");if(holdings){holdings.replaceChildren();for(const h of data.holdings){
    const row=el("li",`${label(data,h.id)} · ${format(h.quantity)} shares · average cost $${format(h.cost)}`);
    holdings.append(row);
   }if(!data.holdings.length){const item=el("li","No holdings yet. Save a listing to your watchlist, then enter your shares and average cost above.");item.className="empty-state";holdings.append(item);}}
   const alerts=$("equity-alerts");if(alerts){alerts.replaceChildren();data.alerts.forEach((a,index)=>{
    const row=el("li",`${label(data,a.id)} · ${a.type} ${a.direction} ${format(a.threshold)} · ${a.triggered?"Condition matched at last check":"Not triggered"}`);
    const remove=el("button","Remove rule");remove.type="button";
    remove.addEventListener("click",()=>change(d=>{const current=d.alerts.findIndex(x=>JSON.stringify(x)===JSON.stringify(a));if(current>=0)d.alerts.splice(current,1);}));row.append(remove);alerts.append(row);
   });if(!data.alerts.length){const item=el("li","No alerts yet. Choose a saved listing and a price or RSI threshold above. Checks run only when you press Check selected listing.");item.className="empty-state";alerts.append(item);}}
  } catch(error) { say(error.message); }
 }
 $("equity-save")?.addEventListener("click",()=>{
  const select=$("stock-options"),id=select.value;
  if(!valid(id)){say("Choose a company or fund first.");return;}
  const option=Array.from(select.options).find(o=>o.value===id);
  try { const data=read();if(data.listings.some(a=>a.id===id)){say("Already saved to your watchlist.");return;}
   if(data.listings.length>=50){say("Watchlist full: remove a listing first.");return;}
   data.listings.push({id,name:option.textContent});save(data);say("Saved to your stock and ETF watchlist in this browser.");
  }catch{say("Watchlist could not be saved. Check browser storage permissions.");}
 });
 $("equity-holding")?.addEventListener("change",()=>{try{$("equity-valuation")?.replaceChildren();const h=read().holdings.find(x=>x.id===$("equity-holding").value);$("equity-quantity").value=h?.quantity??"";$("equity-cost").value=h?.cost??"";}catch{say("Saved holdings could not be read.");}});
 $("equity-holding-form")?.addEventListener("submit",event=>{
  event.preventDefault();const id=$("equity-holding").value,quantity=Number($("equity-quantity").value),cost=Number($("equity-cost").value);
  if(!valid(id)||!Number.isFinite(quantity)||quantity<=0||!Number.isFinite(cost)||cost<0){say("Choose a listing, positive share quantity and nonnegative average cost.");return;}
  change(data=>{if(data.holdings.length>=50&&!data.holdings.some(h=>h.id===id))throw Error();data.holdings=data.holdings.filter(h=>h.id!==id);data.holdings.push({id,quantity,cost});});
 });
 $("equity-remove-holding")?.addEventListener("click",()=>{
  const id=$("equity-holding").value;if(!valid(id))return;
  if(!window.confirm("Remove this saved stock/ETF holding? This does not place a trade."))return;
  change(data=>{data.holdings=data.holdings.filter(h=>h.id!==id);});
 });
 $("equity-alert-form")?.addEventListener("submit",event=>{
  event.preventDefault();const id=$("equity-alert-listing").value,type=$("equity-alert-type").value,direction=$("equity-alert-direction").value,threshold=Number($("equity-alert-threshold").value);
  if(!valid(id)||!["price","rsi"].includes(type)||!["above","below"].includes(direction)||!Number.isFinite(threshold)||threshold<0||(type==="rsi"&&threshold>100)){say("Choose a listing and valid threshold (RSI 0–100).");return;}
  change(data=>{if(data.alerts.length>=50)throw Error();data.alerts.push({id,type,direction,threshold,triggered:false});});
 });
 // Refresh one listing explicitly: never fan out across a large watchlist.
 $("equity-check")?.addEventListener("click",async()=>{
  const id=$("equity-alert-listing").value;if(!valid(id)){say("Choose one saved listing to check.");return;}
  const button=$("equity-check");if(button.disabled)return;button.disabled=true;
  const output=$("equity-check-result");output.replaceChildren();say("Checking completed sessions for the selected listing…");
  try {
   const research=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(id)}&days=90`);
   if($("equity-alert-listing").value!==id)throw new Error("Selection changed. Check the selected listing again.");
   const latest=research.history.at(-1);
   if(!latest||latest.date!==research.window.latest_closed_session)throw new Error("Latest completed-session price is unavailable; alerts were not changed.");
   const data=read();let changed=false;
   for(const a of data.alerts.filter(a=>a.id===id)){
    const value=a.type==="price"?latest.price:research.indicators?.rsi_14;
    if(!Number.isFinite(value)){output.append(el("p",`${a.type}: unavailable; previous state retained.`));continue;}
    const match=a.direction==="above"?value>a.threshold:value<a.threshold;
    output.append(el("p",`${a.type} ${format(value)} on ${latest.date}: ${match?(a.triggered?"still matches":"NEW MATCH"):"condition not met"}.`));
    a.triggered=match;changed=true;
   }
   if(changed)save(data);render();output.append(el("p",`Checked ${new Date().toISOString()} · history fetched ${research.history_source?.fetched_at_utc || "time unavailable"}.`));say("Check complete. Prices are completed-session values, not live quotes.");
  }catch(error){say(error.message);}finally{button.disabled=false;}
 });
 $("equity-value")?.addEventListener("click",async()=>{
  const id=$("equity-holding").value;let holding;
  try{holding=read().holdings.find(h=>h.id===id);}catch{say("Cannot read holdings.");return;}
  if(!holding){say("Choose a saved holding first.");return;}
  const button=$("equity-value");if(button.disabled)return;button.disabled=true;
  const before=JSON.stringify(holding),output=$("equity-valuation");output.replaceChildren();
  try{const research=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(id)}&days=35`);
   if(JSON.stringify(read().holdings.find(h=>h.id===id))!==before||$("equity-holding").value!==id)throw new Error("Holding changed. Load its valuation again.");
   const point=research.history.at(-1);if(!point)throw new Error("No historical price available.");
   output.append(el("p",`${id.split(":").at(-1)} · $${format(point.price*holding.quantity)} estimated value at the ${point.date} close${point.date!==research.window.latest_closed_session?" (older than latest completed session)":""}.`));
   output.append(el("p",holding.cost>0?`Unrealized difference from entered cost: $${format((point.price-holding.cost)*holding.quantity)}. Excludes dividends, fees and taxes.`:"Average cost unknown; gain/loss is unavailable."));
  }catch(error){output.append(el("p",error.message));}finally{button.disabled=false;}
 });

 // Monitoring is opt-in, foreground-only, and serial. A browser-wide lease
 // prevents multiple open pages from multiplying the automatic request rate.
 const monitorStart=$('equity-monitor-start'),monitorStop=$('equity-monitor-stop');
 const monitorStatus=$('equity-monitor-status'),monitorResults=$('equity-monitor-results');
 const leaseKey='research-desk.monitor-attempt.v1';
 let monitoring=false,monitorBusy=false,monitorTimer=null,monitorIndex=0,monitorGeneration=0;
 const observations=new Map();
 function monitorMessage(text){if(monitorStatus)monitorStatus.textContent=text;}
 function stopMonitoring(message='Monitoring stopped. Saved rules remain available.'){
  monitoring=false;monitorGeneration++;if(monitorTimer!==null)clearTimeout(monitorTimer);monitorTimer=null;
  if(monitorStart)monitorStart.disabled=false;if(monitorStop)monitorStop.disabled=true;
  if(message)monitorMessage(message);
 }
 function drawMonitoring(){
  try {
  if(!monitorResults)return;monitorResults.replaceChildren();
  const data=read();for(const listing of data.listings){
   const observation=observations.get(listing.id),row=el('li');
   row.append(el('strong',listing.name));
   if(!observation)row.append(el('p','Not checked on this page yet.'));
   else {
    const price=el('p',`${priceLabel(observation.price)} · close ${observation.session}`);price.className='monitor-price';
    row.append(price,el('p',`Checked ${new Date(observation.checked).toLocaleString()} (your local time).`));
    const freshness=el('details');freshness.append(el('summary','Data freshness'),el('p',`Checked ${observation.checked} · history fetched ${observation.fetched || 'time unavailable'}.`));row.append(freshness);
    for(const text of observation.matches)row.append(el('p',text));
    if(observation.error)row.append(el('p',observation.error));
   }
   const target=el('a','Set a target price or RSI alert');target.href=`/alerts.html?asset=${encodeURIComponent(listing.id)}`;row.append(target);monitorResults.append(row);
  }
  }catch(error){monitorMessage(error.message);}
 }
 async function monitorNext(){
  if(!monitoring||monitorBusy||document.hidden)return;
  monitorBusy=true;const generation=monitorGeneration;let before,data,id,attempted=false;
  try {
   before=localStorage.getItem(key);data=read();
   if(!data.listings.length){stopMonitoring('Save a stock or ETF to your watchlist first.');return;}
   const claim=()=>{const last=Number(localStorage.getItem(leaseKey)||0),now=Date.now();const wait=Number.isFinite(last)&&last<=now?Math.max(0,60000-(now-last)):0;if(!wait)localStorage.setItem(leaseKey,String(now));return wait;};
   const wait=typeof navigator!=='undefined'&&navigator.locks?await navigator.locks.request('research-desk.monitor-slot',claim):claim();
   if(!monitoring||generation!==monitorGeneration||document.hidden)return;
   if(wait>0){monitorMessage('Waiting for the next check; another page checked recently.');monitorTimer=setTimeout(monitorNext,wait);return;}
   id=data.listings[monitorIndex++%data.listings.length].id;
   attempted=true;
   monitorMessage(`Checking ${label(data,id)}. Other listings wait their turn.`);
   const research=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(id)}&days=90`);
   if(!monitoring||generation!==monitorGeneration||document.hidden)return;
   if(localStorage.getItem(key)!==before)throw Error('Watchlist or rules changed during the check. Restart monitoring to use the updated workspace.');
   const latest=research.history.at(-1);
   if(!latest||!Number.isFinite(latest.price)||latest.price<=0||latest.date!==research.window.latest_closed_session)throw Error('Latest completed-session price is unavailable. Saved alert states were retained.');
   const matches=[];let changed=false;
   for(const rule of data.alerts.filter(a=>a.id===id)){
    const value=rule.type==='price'?latest.price:research.indicators?.rsi_14;
    if(!Number.isFinite(value)){matches.push(`${rule.type}: unavailable; saved state retained.`);continue;}
    const match=rule.direction==='above'?value>rule.threshold:value<rule.threshold;
    matches.push(`${rule.type} ${rule.direction} ${format(rule.threshold)}: ${match?(rule.triggered?'Still matches':'NEW MATCH'):'Target not reached'} (${format(value)}).`);
    rule.triggered=match;changed=true;
   }
   if(!matches.length)matches.push('No target rules saved for this listing.');
   if(changed)save(data);
   observations.set(id,{price:latest.price,session:latest.date,checked:new Date().toISOString(),fetched:research.history_source?.fetched_at_utc,matches});
   render();drawMonitoring();monitorMessage('Check complete. Next listing in one minute. Prices are historical closes, not live quotes.');
  }catch(error){
   if(generation===monitorGeneration){stopMonitoring(`Monitoring stopped: ${error.message} Retry manually after the provider is available. Previous successful checks remain visible.`);}
  }finally{
   monitorBusy=false;if(attempted&&monitoring&&generation===monitorGeneration)monitorTimer=setTimeout(monitorNext,60000);
  }
 }
 monitorStart?.addEventListener('click',()=>{
  if(monitoring||monitorBusy)return;monitoring=true;monitorGeneration++;monitorStart.disabled=true;monitorStop.disabled=false;return monitorNext();
 });
 monitorStop?.addEventListener('click',()=>stopMonitoring());
 document.addEventListener?.('visibilitychange',()=>{if(document.hidden&&monitoring)stopMonitoring('Monitoring stopped because this page is hidden. Press Start monitoring when you return.');});
 window.addEventListener('pagehide',()=>stopMonitoring(''));
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null){if(monitoring)stopMonitoring('Workspace changed in another page. Restart monitoring to use it.');observations.clear();drawMonitoring();}});
 if(monitorStart)drawMonitoring();
 window.addEventListener("storage",event=>{if(event.key===key||event.key===null){render();$("equity-valuation")?.replaceChildren();}});
 render();
 const requestedListing=typeof URLSearchParams!=='undefined'&&window.location?new URLSearchParams(window.location.search).get('asset'):null;
 if(valid(requestedListing)&&$('equity-alert-listing')){
  try{if(read().listings.some(a=>a.id===requestedListing))$('equity-alert-listing').value=requestedListing;}catch{say('Saved watchlist could not be read.');}
 }
})();
