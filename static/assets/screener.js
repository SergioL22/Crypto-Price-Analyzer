"use strict";
// Rendering consumes normalized ranking rows. A paid feed can implement the same
// {id,name,as_of,ytd_return,average_volume,price,unavailable} contract later.
(() => {
 const selected=[], rows=[];
 const status=$("screen-status"), output=$("screen-results");
 let busy=false;
 function render() {
  $("screen-list").replaceChildren();
  for(const a of selected){const row=el("li",a.name),remove=el("button","Remove");remove.type="button";remove.disabled=busy;remove.addEventListener("click",()=>{selected.splice(selected.indexOf(a),1);rows.length=0;output.replaceChildren();render();});row.append(remove);$("screen-list").append(row);}
  const order=$("screen-order").value;
  const ranked=rows.filter(r=>!r.unavailable).sort((a,b)=>b[order]-a[order]);
  output.replaceChildren();
  for(const [index,row] of ranked.entries()) output.append(el("p",`${index+1}. ${row.name} · YTD price return ${(row.ytd_return*100).toFixed(2)}% · average daily volume ${format(row.average_volume)} shares · close $${format(row.price)} · through ${row.as_of}`));
  for(const row of rows.filter(r=>r.unavailable))output.append(el("p",`${row.name}: ${row.unavailable}`));
 }
 $("screen-add").addEventListener("click",()=>{
  if(busy)return;const select=$("stock-options"),id=select.value;
  if(!id){status.textContent="Choose a listing above first.";return;}
  if(selected.some(a=>a.id===id))return;
  if(selected.length===5){status.textContent="Compare up to five listings at once to limit free-tier requests.";return;}
  selected.push({id,name:Array.from(select.options).find(o=>o.value===id).textContent});rows.length=0;render();
 });
 $("screen-order").addEventListener("change",render);
 $("screen-run").addEventListener("click",async()=>{
  if(busy||!selected.length)return;busy=true;$("screen-run").disabled=true;$("screen-add").disabled=true;rows.length=0;render();
  // Request enough history to include the previous year's last trading close.
  const now=new Date(),parts=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",year:"numeric",month:"numeric",day:"numeric"}).formatToParts(now);
  const part=type=>Number(parts.find(p=>p.type===type).value),year=part("year");
  const days=Math.ceil((Date.UTC(year,part("month")-1,part("day"))-Date.UTC(year-1,11,15))/86400000)+1;
  let asOf=null;
  try {
   for(const [index,a] of selected.entries()) {
    status.textContent=`Comparing ${index+1} of ${selected.length}. Each listing uses a provider request; no retries.`;
    try {
     const data=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(a.id)}&days=${days}`);
     const bars=data.bars,base=bars.filter(b=>b.date<`${year}-01-01`).at(-1),latest=bars.at(-1);
     if(!base||!latest||latest.date<`${year}-01-01`||!data.window.complete||latest.date!==data.window.latest_closed_session)throw new Error("Complete year-to-date coverage and the prior-year closing baseline are unavailable.");
     if(asOf!==null&&asOf!==latest.date)throw new Error("Different as-of session; run a fresh comparison.");asOf=latest.date;
     const recent=bars.filter(b=>b.date>=`${year}-01-01`);
     rows.push({...a,as_of:latest.date,ytd_return:latest.close/base.close-1,average_volume:recent.reduce((sum,b)=>sum+b.volume,0)/recent.length,price:latest.close});
    }catch(error){rows.push({...a,unavailable:error.message});render();status.textContent="Comparison stopped after a data error to avoid further requests. Available results are partial.";return;}
    render();
   }
   status.textContent=`Compared ${rows.length} selected listings. This is not a whole-market ranking. Price returns exclude dividends.`;
  }finally{busy=false;$("screen-run").disabled=false;$("screen-add").disabled=false;render();}
 });
})();
