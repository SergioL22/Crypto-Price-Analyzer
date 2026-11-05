'use strict';
(()=>{
 const $=id=>document.getElementById(id);
 const SVG='http://www.w3.org/2000/svg';
 const METRICS=['revenue','operating_income','net_income','free_cash_flow','operating_cash_flow','capital_expenditure','eps_diluted','diluted_shares','operating_margin','net_margin'];
 const FUND_DEFAULTS=['SPY','QQQ'];
 const FORM_NAMES={'10-K':'Annual report','10-Q':'Quarterly report','8-K':'Current report (material event)','4':'Insider transaction','DEF 14A':'Proxy statement',
  'SC 13D':'Activist ownership report','SC 13D/A':'Activist ownership amendment','SC 13G':'Passive ownership report','SC 13G/A':'Passive ownership amendment','S-1':'Registration statement','20-F':'Annual report (foreign issuer)','6-K':'Foreign issuer report'};
 // Share classes (e.g. Alphabet A and C) share a name; tell them apart by CUSIP.
 function holdingNames(rows){const counts=new Map();rows.forEach(r=>counts.set(r.name,(counts.get(r.name)||0)+1));return rows.map(r=>counts.get(r.name)>1&&(r.cusip||r.isin)?`${r.name} · ${r.cusip||r.isin}`:r.name);}
 const companies=new Map(),funds=new Map();

 async function api(path){
  const response=await fetch(path,{headers:{Accept:'application/json'}});
  let body=null;try{body=await response.json();}catch{}
  if(!response.ok)throw new Error(body&&body.error?body.error.message:`Request failed (${response.status}).`);
  return body;
 }
 function el(tag,attrs={},text){const node=document.createElement(tag);for(const[k,v]of Object.entries(attrs))node.setAttribute(k,v);if(text!==undefined)node.textContent=text;return node;}
 function svg(tag,attrs={},text){const node=document.createElementNS(SVG,tag);for(const[k,v]of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=text;return node;}
 function option(select,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
 const pct=(v,d=1)=>`${(v*100).toFixed(d)}%`;
 function money(v){const a=Math.abs(v),s=v<0?'−':'';if(a>=1e12)return`${s}$${(a/1e12).toFixed(2)}T`;if(a>=1e9)return`${s}$${(a/1e9).toFixed(1)}B`;if(a>=1e6)return`${s}$${(a/1e6).toFixed(0)}M`;return`${s}$${a.toLocaleString('en-US')}`;}
 function format(v,unit){if(unit==='ratio')return pct(v);if(unit==='USD/shares')return`${v<0?'−':''}$${Math.abs(v).toFixed(2)}`;if(unit==='shares')return v>=1e9?`${(v/1e9).toFixed(2)}B`:`${(v/1e6).toFixed(0)}M`;return money(v);}
 const fy=row=>`FY${row.period_end.slice(0,4)}`;
 const filingFolder=(cik,accession)=>`https://www.sec.gov/Archives/edgar/data/${cik}/${accession.replace(/-/g,'')}/`;

 function drawChart(metric){
  const root=$('metric-chart');root.replaceChildren();
  const rows=metric.values;
  if(!rows.length){root.append(el('p',{},`${metric.label} is not reported in this company's filings under the standard tags we read.`));return;}
  const W=640,H=250,L=8,R=8,T=22,B=26,values=rows.map(r=>r.value);
  const max=Math.max(0,...values),min=Math.min(0,...values),span=(max-min)||1;
  const y=v=>T+(max-v)/span*(H-T-B),zero=y(0),slot=(W-L-R)/rows.length,bw=Math.min(44,slot*.62);
  const chart=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'presentation'});
  [max,max/2,min<0?min:null].filter(v=>v!==null&&v!==0).forEach(v=>chart.append(svg('line',{class:'grid',x1:L,x2:W-R,y1:y(v),y2:y(v)})));
  rows.forEach((row,i)=>{
   const x=L+slot*i+(slot-bw)/2,top=Math.min(y(row.value),zero),height=Math.max(1,Math.abs(y(row.value)-zero));
   const bar=svg('rect',{class:`bar${row.value<0?' negative':''}${i===rows.length-1?' latest':''}`,x,y:top,width:bw,height,rx:2});
   bar.append(svg('title',{},`${fy(row)}: ${format(row.value,metric.unit)}`));chart.append(bar);
   if(rows.length<=10)chart.append(svg('text',{class:'value',x:x+bw/2,y:row.value<0?top+height+12:top-5,'text-anchor':'middle'},format(row.value,metric.unit)));
   chart.append(svg('text',{x:x+bw/2,y:H-8,'text-anchor':'middle'},fy(row)));
  });
  chart.append(svg('line',{class:'axis',x1:L,x2:W-R,y1:zero,y2:zero}));
  root.append(chart);
  root.setAttribute('aria-label',`${metric.label}, ${rows.length} fiscal years, latest ${format(rows[rows.length-1].value,metric.unit)} in ${fy(rows[rows.length-1])}.`);
 }

 function renderMetric(){
  const company=companies.get($('company').value);if(!company)return;
  const metric=company.metrics[$('metric').value];
  drawChart(metric);
  $('metric-caption').textContent=metric.derived?`Calculated by Research Desk from reported values (${metric.values[0]?metric.values[0].concept.replace(/_/g,' '):'no matching years'}).`:'As reported to the SEC in XBRL filings. Years follow each fiscal year’s end date.';
  const body=$('metric-table').tBodies[0];body.replaceChildren();
  [...metric.values].reverse().forEach((row,i,list)=>{
   const tr=el('tr'),prev=list[i+1];
   tr.append(el('td',{},`${row.period_end} (${fy(row)})`),el('td',{class:'num'},format(row.value,metric.unit)));
   let change='—',cls='';
   if(prev&&metric.unit!=='ratio'&&prev.value>0){const c=row.value/prev.value-1;change=`${c>=0?'+':'−'}${Math.abs(c*100).toFixed(1)}%`;cls=c>=0?'up':'down';}
   else if(prev&&metric.unit==='ratio'){const c=(row.value-prev.value)*100;change=`${c>=0?'+':'−'}${Math.abs(c).toFixed(1)} pts`;cls=c>=0?'up':'down';}
   const td=el('td',{class:`num ${cls}`},change);tr.append(td);
   const source=el('td');
   if(row.accession){const a=el('a',{href:filingFolder(company.cik,row.accession),target:'_blank',rel:'noopener noreferrer'},`${row.form||'Filing'} · ${row.accession}`);source.append(a);}else source.textContent='Calculated';
   tr.append(source);body.append(tr);
  });
 }

 function resetInsiders(){$('insider-stats').replaceChildren();$('insider-status').textContent='';$('insider-people-box').hidden=true;$('insider-recent-box').hidden=true;$('insider-load').disabled=false;}
 async function loadInsiders(){
  const symbol=$('company').value,status=$('insider-status');$('insider-load').disabled=true;
  status.textContent=`Reading ${symbol}'s Form 4 filings at the SEC… The first load can take up to 20 seconds.`;
  try{
   const d=await api(`/v1/sec/insiders?symbol=${encodeURIComponent(symbol)}`);
   if($('company').value!==symbol)return;
   status.textContent=`${d.forms} Form 4 filings since ${d.since}${d.truncated?' (latest 40 read)':''} · checked ${d.fetched_at_utc.slice(0,16).replace('T',' ')} UTC.`;
   const stats=$('insider-stats');stats.replaceChildren();
   stat(stats,'Open-market buys',`${d.buys.count} · ${money(d.buys.value)}`);
   stat(stats,'Open-market sales',`${d.sales.count} · ${money(d.sales.value)}`);
   stat(stats,'Sales under a 10b5-1 plan',d.sales.count?`${d.sales.planned} of ${d.sales.count}`:'—');
   stat(stats,'Other transactions',String(d.other_transactions));
   const people=$('insider-people').tBodies[0];people.replaceChildren();
   d.insiders.forEach(p=>{const tr=el('tr');tr.append(el('td',{},p.insider),el('td',{},p.roles.join(', ')||'—'),el('td',{class:'num'},p.bought?money(p.bought):'—'),el('td',{class:'num'},p.sold?money(p.sold):'—'));people.append(tr);});
   $('insider-people-box').hidden=!d.insiders.length;
   const recent=$('insider-recent').tBodies[0];recent.replaceChildren();
   d.recent.forEach(r=>{const tr=el('tr'),link=el('td');link.append(el('a',{href:r.url,target:'_blank',rel:'noopener noreferrer'},r.filed));
    tr.append(el('td',{},r.date),el('td',{},r.insider),el('td',{},`${r.label}${r.planned&&r.code==='S'?' (10b5-1 plan)':''}`),el('td',{class:'num'},Math.round(r.shares).toLocaleString('en-US')),
     el('td',{class:'num'},r.price?`$${r.price.toFixed(2)}`:'—'),link);recent.append(tr);});
   $('insider-recent-box').hidden=!d.recent.length;
   if(!d.recent.length)status.textContent+=' No insider transactions in this period.';
  }catch(error){status.textContent=error.message;$('insider-load').disabled=false;}
 }
 async function loadCompany(){
  const symbol=$('company').value;$('company-status').textContent=`Loading ${symbol}…`;
  try{
   const company=companies.get(symbol)||await api(`/v1/sec/company?symbol=${encodeURIComponent(symbol)}`);companies.set(symbol,company);
   $('company-status').textContent='';resetInsiders();
   const meta=$('company-meta');meta.replaceChildren();
   meta.append(`${company.registrant||company.name} · CIK ${company.cik}${company.sic_description?` · ${company.sic_description}`:''} · `);
   meta.append(el('a',{href:company.source_url,target:'_blank',rel:'noopener noreferrer'},'All filings on EDGAR'));
   if(company.note)meta.append(el('span',{class:'note'},` ${company.note}`));
   renderMetric();
   const list=$('filings');list.replaceChildren();
   company.filings.slice(0,12).forEach(f=>{
    const li=el('li');li.append(el('span',{class:'form'},f.form),el('time',{datetime:f.filed},f.filed));
    const generic=!f.description||f.description.replace(/^FORM\s+/i,'').toUpperCase()===f.form.toUpperCase();
    const label=generic?`${FORM_NAMES[f.form]||`${f.form} filing`}${f.report_date?` · period ${f.report_date}`:''}`:f.description;
    li.append(el('a',{href:f.url,target:'_blank',rel:'noopener noreferrer'},label));
    list.append(li);
   });
   if(!company.filings.length)list.append(el('li',{},'No recent filings of these types.'));
  }catch(error){$('company-status').textContent=error.message;}
 }

 function stat(root,label,value){const d=el('div');d.append(el('dt',{},label),el('dd',{},value));root.append(d);}
 function weightCell(value,max){const td=el('td',{class:'num'}),wrap=el('div',{class:'weight'});wrap.append(el('meter',{min:'0',max:String(max),value:String(value),'aria-hidden':'true'}),el('span',{},pct(value,2)));td.append(wrap);return td;}

 async function loadFund(){
  const symbol=$('fund').value;$('fund-status').textContent=`Loading ${symbol} holdings…`;
  try{
   const fund=funds.get(symbol)||await api(`/v1/sec/fund?symbol=${encodeURIComponent(symbol)}`);funds.set(symbol,fund);
   const s=fund.summary;
   const status=$('fund-status');status.replaceChildren(`${fund.name} · holdings as of ${fund.period_end}, filed ${fund.filed} · `);
   status.append(el('a',{href:fund.filing_url,target:'_blank',rel:'noopener noreferrer'},'Form N-PORT on EDGAR'));
   const stats=$('fund-stats');stats.replaceChildren();
   stat(stats,'Holdings',s.holding_count.toLocaleString('en-US'));
   stat(stats,'Top 10 weight',pct(s.top10_weight));
   stat(stats,'Effective holdings',s.effective_holdings===null?'—':Math.round(s.effective_holdings).toLocaleString('en-US'));
   stat(stats,'Net assets',money(fund.net_assets_usd));
   if(s.short_term_vehicles_weight>0.0005)stat(stats,'Cash vehicles (excluded)',pct(s.short_term_vehicles_weight));
   const body=$('fund-table').tBodies[0];body.replaceChildren();const max=s.top_holdings.length?s.top_holdings[0].weight:1;
   const names=holdingNames(s.top_holdings);
   s.top_holdings.forEach((h,i)=>{const tr=el('tr');tr.append(el('td',{class:'num'},String(i+1)),el('td',{},names[i]),weightCell(h.weight,max));body.append(tr);});
  }catch(error){$('fund-status').textContent=error.message;}
 }

 async function loadOverlap(){
  const a=$('fund-a').value,b=$('fund-b').value,status=$('overlap-status'),stats=$('overlap-stats'),body=$('overlap-table').tBodies[0];
  stats.replaceChildren();body.replaceChildren();
  if(a===b){status.textContent='Choose two different ETFs.';return;}
  status.textContent=`Comparing ${a} and ${b}…`;
  try{
   const o=await api(`/v1/sec/overlap?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
   status.textContent=`${a} holdings as of ${o.a.period_end}; ${b} holdings as of ${o.b.period_end}.`;
   stat(stats,'Overlap by weight',pct(o.weight_overlap));
   stat(stats,`${a} also held by ${b}`,pct(o.a_weight_in_b));
   stat(stats,`${b} also held by ${a}`,pct(o.b_weight_in_a));
   stat(stats,'Shared holdings',`${o.shared_count.toLocaleString('en-US')} of ${o.count_a.toLocaleString('en-US')} / ${o.count_b.toLocaleString('en-US')}`);
   $('overlap-a-head').textContent=`In ${a}`;$('overlap-b-head').textContent=`In ${b}`;
   const max=o.top_shared.length?Math.max(...o.top_shared.map(r=>Math.max(r.weight_a,r.weight_b))):1;
   const names=holdingNames(o.top_shared);
   o.top_shared.forEach((r,i)=>{const tr=el('tr');tr.append(el('td',{},names[i]),weightCell(r.weight_a,max),weightCell(r.weight_b,max),el('td',{class:'num'},pct(r.overlap,2)));body.append(tr);});
   if(!o.top_shared.length){const tr=el('tr');tr.append(el('td',{colspan:'4'},'These funds share no holdings.'));body.append(tr);}
  }catch(error){status.textContent=error.message;}
 }

 async function start(){
  document.querySelectorAll('nav a').forEach(a=>{if(new URL(a.href).pathname===location.pathname)a.setAttribute('aria-current','page');});
  try{
   const coverage=await api('/v1/sec/coverage');
   $('sec-notice').textContent=coverage.notice;
   $('sec-updated').textContent=`Snapshot built ${coverage.generated_at_utc.slice(0,10)}.`;
   coverage.companies.forEach(c=>option($('company'),c.symbol,`${c.name} · ${c.symbol}`));
   coverage.funds.forEach(f=>{for(const id of['fund','fund-a','fund-b'])option($(id),f.symbol,`${f.symbol} · ${f.name}`);});
   const sample=await api(`/v1/sec/company?symbol=${encodeURIComponent(coverage.companies[0].symbol)}`);companies.set(sample.symbol,sample);
   METRICS.filter(k=>sample.metrics[k]).forEach(k=>option($('metric'),k,sample.metrics[k].label));
   $('fund-a').value=FUND_DEFAULTS[0];$('fund-b').value=FUND_DEFAULTS[1];
   $('lookup-form').onsubmit=async e=>{
    e.preventDefault();const symbol=$('lookup-symbol').value.trim().toUpperCase();
    if(!/^[A-Z]{1,5}([.-][A-Z]{1,2})?$/.test(symbol)){$('company-status').textContent='Enter a US ticker such as TSLA or BRK.B.';return;}
    $('company-status').textContent=`Looking up ${symbol} at the SEC… This can take a few seconds the first time.`;
    try{
     const company=await api(`/v1/sec/lookup?symbol=${encodeURIComponent(symbol)}`);companies.set(company.symbol,company);
     if(![...$('company').options].some(o=>o.value===company.symbol))option($('company'),company.symbol,`${company.name} · ${company.symbol}`);
     $('company').value=company.symbol;$('lookup-symbol').value='';await loadCompany();
    }catch(error){$('company-status').textContent=error.message;}
   };
   $('insider-load').onclick=loadInsiders;
   $('company').onchange=loadCompany;$('metric').onchange=renderMetric;$('fund').onchange=loadFund;$('fund-a').onchange=loadOverlap;$('fund-b').onchange=loadOverlap;
   await Promise.all([loadCompany(),loadFund(),loadOverlap()]);
  }catch(error){$('company-status').textContent=error.message;$('fund-status').textContent='';$('overlap-status').textContent='';}
 }
 start();
})();
