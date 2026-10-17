"use strict";
// Replaceable feed contract. No subscription, provider switch or paid calls here.
const ScreeningFeed = (() => {
 const capabilities=Object.freeze({provider:typeof researchSourceLabel==='function'?researchSourceLabel():'Twelve Data history',universe:'selected_list',max_listings:5,
  periods:['ytd','1m','6m','1y'],metrics:['return_fraction','average_volume','price'],
  unavailable:['revenue','market_cap','industry','dividend_yield','expense_ratio']});
 function window(period,now=new Date()){
  if(!capabilities.periods.includes(period))throw Error('Unsupported comparison period.');
  const parts=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'numeric',day:'numeric'}).formatToParts(now);
  const part=t=>Number(parts.find(p=>p.type===t).value),year=part('year'),today=Date.UTC(year,part('month')-1,part('day'));
  return {year,days:period==='ytd'?Math.ceil((today-Date.UTC(year-1,11,15))/86400000)+1:({'1m':30,'6m':183,'1y':365}[period]+16)};
 }
 function row(asset,data,period,year){
  const bars=data.bars,latest=bars?.at(-1);
  if(!Array.isArray(bars)||!latest||!data.window?.complete||latest.date!==data.window.latest_closed_session)throw Error('Complete coverage through the latest closed session is unavailable.');
  const cutoff=period==='ytd'?`${year}-01-01`:new Date(Date.parse(latest.date)-{'1m':30,'6m':183,'1y':365}[period]*86400000).toISOString().slice(0,10);
  const base=bars.filter(b=>period==='ytd'?b.date<cutoff:b.date<=cutoff).at(-1);
  if(!base||base.date>=latest.date||(period==='ytd'&&latest.date<cutoff))throw Error('The selected-period closing baseline is unavailable.');
  if(bars.some((b,i)=>!/^\d{4}-\d{2}-\d{2}$/.test(b.date)||!Number.isFinite(b.close)||b.close<=0||!Number.isFinite(b.volume)||b.volume<0||(i&&bars[i-1].date>=b.date)))throw Error('Invalid historical prices or share volume.');
  const recent=bars.filter(b=>b.date>base.date),returns=latest.close/base.close-1,volume=recent.reduce((sum,b)=>sum+b.volume,0)/recent.length;
  if(!Number.isFinite(returns)||!Number.isFinite(volume))throw Error('Comparison metrics are unavailable.');
  return {...asset,asset_class:asset.id.split(':')[1]||'unknown',as_of:latest.date,start:base.date,period,return_fraction:returns,
   ytd_return:period==='ytd'?returns:null,average_volume:volume,price:latest.close,revenue:null,market_cap:null,industry:null,
   fetched_at_utc:data.history_source?.fetched_at_utc||null,cache_hit:Boolean(data.history_source?.cache_hit)};
 }
 function selectedHistory(request){return {capabilities,async screen({listings,period='ytd',onRow=()=>{},isCurrent=()=>true}){
  if(!Array.isArray(listings)||!listings.length||listings.length>capabilities.max_listings||new Set(listings.map(a=>a.id)).size!==listings.length)throw Error('Choose one to five different listings.');
  const {year,days}=window(period),rows=[];let asOf=null,start=null;
  for(const asset of listings){
   if(!isCurrent())return {capabilities,rows,cancelled:true,complete:false};
   try{
    const data=await request(`/v1/stock-analysis?asset_id=${encodeURIComponent(asset.id)}&days=${days}`);
    if(!isCurrent())return {capabilities,rows,cancelled:true,complete:false};
    const result=row(asset,data,period,year);
    if((asOf!==null&&asOf!==result.as_of)||(start!==null&&start!==result.start))throw Error('Comparison dates differ; no comparable ranking was estimated for this listing.');
    asOf=result.as_of;start=result.start;rows.push(result);onRow(result);
   }catch(error){const failure={...asset,unavailable:error.message};rows.push(failure);onRow(failure);return {capabilities,rows,complete:false,as_of:asOf,start};}
  }
  return {capabilities,rows,complete:true,as_of:asOf,start};
 }};}
 return {capabilities,window,row,selectedHistory};
})();
