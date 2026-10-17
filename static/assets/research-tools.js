"use strict";
// Research illustrations only. No orders, AI requests or invented prices.
const ResearchReturns = (() => {
 const day=86400000;
 function date(value){if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value))||new Date(value).toISOString().slice(0,10)!==value)throw Error('Choose a valid date.');return value;}
 function days(start,now=new Date()){date(start);const n=Math.ceil((Date.parse(now.toISOString().slice(0,10))-Date.parse(start))/day)+2;if(n<2)throw Error('Choose a date no later than today.');if(n>3660)throw Error('This illustration supports up to ten years. Choose a more recent date.');return n;}
 function series(data,start,after=false){
  date(start);const history=data.history;
  if(!Array.isArray(history)||!history.length)throw Error('No historical prices are available.');
  let prior='';for(const p of history){date(p.date);if(p.date<=prior||!Number.isFinite(p.price)||p.price<=0)throw Error('Historical prices are invalid.');prior=p.date;}
  const points=history.filter(p=>after?p.date>start:p.date>=start),first=points[0],last=points.at(-1);
  if(!first||!last||last.date!==data.window?.latest_closed_session)throw Error('The latest completed session is unavailable.');
  if(Date.parse(first.date)-Date.parse(start)>7*day)throw Error('The requested starting period is unavailable; a later price was not substituted.');
  if(!Array.isArray(data.window?.missing_sessions))throw Error('Trading-session coverage could not be verified.');
  if(data.window.missing_sessions.some(d=>(after?d>start:d>=start)&&d<=last.date))throw Error('Trading sessions are missing in this period. No return was estimated.');
  return points;
 }
 function result(points,amount){
  if(!Number.isFinite(amount)||amount<=0)throw Error('Enter a positive imaginary amount.');
  const first=points[0],last=points.at(-1),shares=amount/first.price,value=shares*last.price,change=value-amount,percent=(last.price/first.price-1)*100;
  if(![shares,value,change,percent].every(Number.isFinite))throw Error('This calculation exceeds the supported numeric range.');
  return {shares,value,change,percent,start:first.date,end:last.date};
 }
 function chart(parent,points,amount,title){
  const base=points[0].price,scaled=points.map(p=>({...p,price:amount===null?p.price:p.price/base*amount,ma_7:null,ma_25:null,bollinger_lower:null,bollinger_middle:null,bollinger_upper:null}));
  if(scaled.length>1)priceChart(parent,scaled,{sessions:true,title});
 }
 return {date,days,series,result,chart};
})();

function watchPerformancePanel(root,listing,current,startTracking){
 const details=el('details');details.append(el('summary','Performance since saving'));root.append(details);
 if(!listing.saved_on){details.append(el('p','This older entry has no recorded save date. Its original starting price cannot be reconstructed reliably.'));const start=el('button','Start tracking from today');start.type='button';start.addEventListener('click',startTracking);details.append(start);return;}
 details.append(el('p',`Saved ${listing.saved_on} (UTC). Comparison starts with the first completed trading session after that date. It is a price change, not an investment return including dividends.`));
 const button=el('button','Load performance'),output=el('div');button.type='button';output.setAttribute('role','status');details.append(button,output);let busy=false;
 button.addEventListener('click',async()=>{
  if(busy)return;busy=true;button.disabled=true;output.replaceChildren(el('p','Loading adjusted historical prices…'));
  const valid=()=>current()?.saved_on===listing.saved_on&&(!root.contains||root.contains(output));
  try{
   const days=ResearchReturns.days(listing.saved_on),data=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(listing.id)}&days=${days}`);
   if(!valid())return;
   const points=ResearchReturns.series(data,listing.saved_on,true),first=points[0],last=points.at(-1),change=last.price-first.price,percent=change/first.price*100;
   if(!Number.isFinite(percent))throw Error('Price change cannot be represented.');
   output.replaceChildren(el('p',`${percent>=0?'+':''}${percent.toFixed(2)}% · ${change>=0?'+':''}${priceLabel(change)} per share · ${first.date} to ${last.date}`));
   output.append(el('p',`Starting close ${priceLabel(first.price)} · latest close ${priceLabel(last.price)}. Both prices come from the same split-adjusted history response; the starting value may be restated after a split. History retrieved ${data.history_source?.fetched_at_utc||'time unavailable'}${data.history_source?.cache_hit?' (cached)':''}.`));
   ResearchReturns.chart(output,points,null,'Watchlist closing prices · USD');
  }catch(error){if(valid())output.replaceChildren(el('p',error.message));}finally{busy=false;button.disabled=false;}
 });
}

(() => {
 const form=$('simulation-form');if(!form)return;
 const asset=$('simulation-asset'),benchmark=$('simulation-benchmark'),output=$('simulation-results'),status=$('simulation-status');
 let listings=[];
 try{
  const raw=JSON.parse(localStorage.getItem('research-desk.equities.v1')||'{"listings":[]}');
  if(!Array.isArray(raw.listings)||raw.listings.length>50)throw Error();
  listings=raw.listings.filter(a=>typeof a.name==='string'&&a.name.length<=500&&/^twelvedata:(stock|etf):(XNYS|XNAS|XNGS|XNMS|XNCM|ARCX|XASE|BATS):USD:[A-Za-z0-9.^_-]{1,100}$/.test(a.id));
 }catch{status.textContent='Saved listings could not be read. Your existing workspace was not changed.';}
 for(const [picker,prompt]of [[asset,'Choose a saved stock or ETF'],[benchmark,'No comparison']]){const option=el('option',prompt);option.value='';picker.append(option);for(const a of listings){const o=el('option',a.name);o.value=a.id;picker.append(o);}}
 const today=new Date().toISOString().slice(0,10);$('simulation-date').max=today;
 let busy=false,generation=0;for(const id of ['simulation-asset','simulation-benchmark','simulation-amount','simulation-date'])$(id).addEventListener('input',()=>{generation++;output.replaceChildren();status.textContent='Inputs changed. Calculate again to see the matching result.';});
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;const selected=asset.value,compare=benchmark.value,amount=Number($('simulation-amount').value),start=$('simulation-date').value,revision=++generation;
  output.replaceChildren();
  try{
   if(!listings.some(a=>a.id===selected)||(compare&&!listings.some(a=>a.id===compare)))throw Error('Choose a saved stock or ETF.');
   if(!Number.isFinite(amount)||amount<=0)throw Error('Enter a positive imaginary amount.');
   const days=ResearchReturns.days(start);busy=true;const submit=form.querySelector('button[type="submit"]');if(submit)submit.disabled=true;
   status.textContent='Calculating from historical closes…';
   const data=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(selected)}&days=${days}`);if(revision!==generation)return;
   const points=ResearchReturns.series(data,start),result=ResearchReturns.result(points,amount);let comparison=null,other=null;
   if(compare){other=compare===selected?data:await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(compare)}&days=${days}`);if(revision!==generation)return;const p=ResearchReturns.series(other,start);if(p.length!==points.length||p.some((v,i)=>v.date!==points[i].date))throw Error('Comparison dates do not match. No comparison was estimated.');comparison=ResearchReturns.result(p,amount);}
   const name=id=>listings.find(a=>a.id===id).name;
   const cards=el('div');cards.className='simulation-summary';
   const card=(label,value,kind)=>{const box=el('article'),number=el('p',value);box.className=`simulation-metric ${kind}`;number.className='simulation-value';box.append(el('h3',label),number);cards.append(box);return box;};
   card('Final hypothetical value',priceLabel(result.value),'simulation-final').append(el('p',`At the ${result.end} close`));
   const gain=card(result.change<0?'Hypothetical loss':'Hypothetical gain',`${result.change>0?'+':''}${priceLabel(result.change)}`,result.change<0?'return-negative':result.change>0?'return-positive':'return-flat');
   const percent=el('p',`${result.percent>0?'+':''}${result.percent.toFixed(2)}%`);percent.className='simulation-percent';gain.append(percent);
   card('Starting amount',priceLabel(amount),'simulation-start').append(el('p',`At the ${result.start} close`));
   output.append(el('h3',name(selected)),cards,el('p',`${result.start} to ${result.end} · ${format(result.shares)} split-adjusted equivalent fractional shares. Historical prices are adjusted for splits; no shares are actually bought. Both endpoints use one adjustment basis.`));
   if(comparison)output.append(el('h3',`Comparison: ${name(compare)}`),el('p',`${priceLabel(amount)} → ${priceLabel(comparison.value)} (${comparison.percent.toFixed(2)}%) on matching sessions. Difference in ending value: ${priceLabel(result.value-comparison.value)}.`));
   ResearchReturns.chart(output,points,amount,'Hypothetical investment value · USD');
   output.append(el('p',`Source: Twelve Data split-adjusted daily history. Retrieved ${data.history_source?.fetched_at_utc||'time unavailable'}${data.history_source?.cache_hit?' (cached)':''}. Excludes dividends, fees, taxes and slippage. Past performance does not predict future results.`));
   status.textContent='Hypothetical calculation complete. No trade or position was saved.';
  }catch(error){if(revision===generation){output.replaceChildren();status.textContent=error.message;}}finally{busy=false;const submit=form.querySelector('button[type="submit"]');if(submit)submit.disabled=false;}
 });
})();
