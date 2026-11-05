'use strict';
(()=>{
 const $=id=>document.getElementById(id);
 const KEY='research-desk.filing-alerts.v1',WATCHLIST_KEY='research-desk.public-market.watchlist.v1';
 const TYPES=[
  ['reports','Annual and quarterly reports',['10-K','10-Q','20-F','6-K']],
  ['events','Material events (8-K)',['8-K']],
  ['insider','Insider trades (Form 4)',['4']],
  ['ownership','Ownership, proxy and offerings',['SC 13D','SC 13D/A','SC 13G','SC 13G/A','DEF 14A','S-1']]];
 const FORM_NAMES={'10-K':'Annual report','10-Q':'Quarterly report','8-K':'Material event','4':'Insider transaction','DEF 14A':'Proxy statement','SC 13D':'Activist ownership report','SC 13D/A':'Activist ownership amendment','SC 13G':'Passive ownership report','SC 13G/A':'Passive ownership amendment','S-1':'Registration statement','20-F':'Annual report (foreign issuer)','6-K':'Foreign issuer report'};
 const MAX_SEEN=60;
 let state={follow:[],types:TYPES.map(t=>t[0]),seen:{}},covered=[],latest=[],storageOk=true;

 function load(){
  try{const raw=JSON.parse(localStorage.getItem(KEY)||'null');
   if(raw&&Array.isArray(raw.follow))state={follow:raw.follow.filter(s=>typeof s==='string'),types:Array.isArray(raw.types)?raw.types:state.types,seen:raw.seen&&typeof raw.seen==='object'?raw.seen:{}};
   else state.follow=watchlistSymbols();
  }catch{storageOk=false;}
 }
 function save(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch{storageOk=false;}}
 function watchlistSymbols(){
  try{const list=JSON.parse(localStorage.getItem(WATCHLIST_KEY)||'[]');return Array.isArray(list)?list.map(s=>String(s).split(':').pop()):[];}catch{return[];}
 }
 function el(tag,attrs={},text){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
 const typeOf=form=>(TYPES.find(t=>t[2].includes(form))||[null])[0];
 const time=iso=>new Date(iso).toLocaleString([], {dateStyle:'medium',timeStyle:'short'});

 function renderControls(){
  const follow=$('alert-follow');follow.replaceChildren();
  covered.forEach(c=>{
   const id=`follow-${c.symbol}`,label=el('label',{for:id,class:'check'}),box=el('input',{type:'checkbox',id});
   box.checked=state.follow.includes(c.symbol);
   box.onchange=()=>{state.follow=box.checked?[...new Set([...state.follow,c.symbol])]:state.follow.filter(s=>s!==c.symbol);save();check();};
   label.append(box,` ${c.name} · ${c.symbol}`);follow.append(label);
  });
  const types=$('alert-types');types.replaceChildren();
  TYPES.forEach(([key,label])=>{
   const id=`type-${key}`,wrap=el('label',{for:id,class:'check'}),box=el('input',{type:'checkbox',id});
   box.checked=state.types.includes(key);
   box.onchange=()=>{state.types=box.checked?[...new Set([...state.types,key])]:state.types.filter(t=>t!==key);save();render();};
   wrap.append(box,` ${label}`);types.append(wrap);
  });
  const fromWatchlist=watchlistSymbols().filter(s=>covered.some(c=>c.symbol===s)&&!state.follow.includes(s));
  $('alert-watchlist').hidden=!fromWatchlist.length;
  $('alert-watchlist').textContent=`Follow ${fromWatchlist.length} compan${fromWatchlist.length===1?'y':'ies'} from your market watchlist`;
  $('alert-watchlist').onclick=()=>{state.follow=[...new Set([...state.follow,...fromWatchlist])];save();renderControls();check();};
 }

 function render(){
  const list=$('alert-list');list.replaceChildren();
  const rows=latest.flatMap(c=>c.filings.map(f=>({...f,symbol:c.symbol,name:c.name,isNew:!(state.seen[c.symbol]||[]).includes(f.accession)})))
   .filter(f=>state.types.includes(typeOf(f.form)))
   .sort((a,b)=>b.filed.localeCompare(a.filed)||a.symbol.localeCompare(b.symbol)).slice(0,30);
  const fresh=rows.filter(r=>r.isNew).length;
  $('alert-count').textContent=!state.follow.length?'':fresh?`${fresh} new filing${fresh===1?'':'s'} since you last marked them seen.`:'No new filings since you last checked.';
  $('alert-seen').disabled=!fresh;
  if(!state.follow.length){list.append(el('li',{class:'empty'},'Follow a company above to see its SEC filings here.'));return;}
  if(!rows.length){list.append(el('li',{class:'empty'},'No recent filings match the selected types.'));return;}
  rows.forEach(f=>{
   const li=el('li');if(f.isNew)li.append(el('span',{class:'badge'},'NEW'));
   li.append(el('span',{class:'form'},f.form),el('time',{datetime:f.filed},f.filed),el('strong',{},f.symbol));
   li.append(el('a',{href:f.url,target:'_blank',rel:'noopener noreferrer'},`${f.name}: ${FORM_NAMES[f.form]||`${f.form} filing`}${f.report_date?` · period ${f.report_date}`:''}`));
   list.append(li);
  });
 }

 async function check(){
  const status=$('alert-status');latest=[];
  if(!state.follow.length){status.textContent=storageOk?'':'Browser storage is unavailable, so followed companies will not be remembered.';render();return;}
  status.textContent='Checking SEC filings…';
  try{
   const response=await fetch(`/v1/sec/filings?symbols=${encodeURIComponent(state.follow.join(','))}`,{headers:{Accept:'application/json'}});
   const body=await response.json().catch(()=>null);
   if(!response.ok)throw new Error(body&&body.error?body.error.message:`Request failed (${response.status}).`);
   latest=body.companies;
   // A newly followed company starts with its current filings marked as seen, so only later filings show as new.
   latest.forEach(c=>{if(!state.seen[c.symbol])state.seen[c.symbol]=c.filings.map(f=>f.accession).slice(0,MAX_SEEN);});save();
   const live=latest.filter(c=>c.filings_source==='live');
   status.textContent=live.length===latest.length?`Checked with the SEC at ${time(live[0].filings_fetched_at_utc)} (refreshed at most every 30 minutes).`
    :`Live check unavailable; showing filings from the snapshot built ${latest[0]?latest[0].filings_fetched_at_utc.slice(0,10):'earlier'}.`;
   if(!storageOk)status.textContent+=' Browser storage is unavailable, so seen filings will not be remembered.';
  }catch(error){status.textContent=error.message;}
  render();
 }

 async function start(){
  if(!$('filing-alerts'))return;
  load();
  try{
   const response=await fetch('/v1/sec/coverage',{headers:{Accept:'application/json'}});if(!response.ok)throw new Error();
   covered=(await response.json()).companies;
  }catch{$('alert-status').textContent='Filing alerts are unavailable right now.';return;}
  state.follow=state.follow.filter(s=>covered.some(c=>c.symbol===s));
  renderControls();
  $('alert-seen').onclick=()=>{latest.forEach(c=>{state.seen[c.symbol]=[...new Set([...c.filings.map(f=>f.accession),...(state.seen[c.symbol]||[])])].slice(0,MAX_SEEN);});save();render();};
  $('alert-refresh').onclick=check;
  await check();
 }
 start();
})();
