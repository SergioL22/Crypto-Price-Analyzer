'use strict';
// Pure calculations for the "Your price data" page. Everything runs in the visitor's
// browser on a file they supply; Research Desk never receives or stores the prices.
(function(root){
 const DAY=86400000,TRADING_DAYS=252,MAX_ROWS=20000;

 function splitLine(line){
  const out=[];let cur='',quoted=false;
  for(let i=0;i<line.length;i++){
   const c=line[i];
   if(quoted){if(c==='"'&&line[i+1]==='"'){cur+='"';i++;}else if(c==='"')quoted=false;else cur+=c;}
   else if(c==='"')quoted=true;else if(c===','||c===';'||c==='\t'){out.push(cur);cur='';}else cur+=c;
  }
  out.push(cur);return out.map(s=>s.trim());
 }
 function parseDate(text){
  let m=/^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(text),y,mo,d;
  if(m)[y,mo,d]=[+m[1],+m[2],+m[3]];
  else if((m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text)))[y,mo,d]=[+m[3],+m[1],+m[2]];   // US month/day/year
  else return null;
  const t=Date.UTC(y,mo-1,d),check=new Date(t);
  if(check.getUTCFullYear()!==y||check.getUTCMonth()!==mo-1||check.getUTCDate()!==d)return null;
  return check.toISOString().slice(0,10);
 }
 function parseNumber(text){
  const clean=String(text).replace(/[$,\s]/g,'');
  if(!/^-?\d*\.?\d+(e-?\d+)?$/i.test(clean))return NaN;
  return Number(clean);
 }
 function parseCsv(text){
  const lines=String(text).replace(/^﻿/,'').split(/\r?\n/).filter(l=>l.trim());
  if(lines.length<3)throw new Error('The file needs a header row and at least two rows of prices.');
  const header=splitLine(lines[0]).map(h=>h.toLowerCase().replace(/[^a-z]/g,''));
  const dateCol=header.findIndex(h=>['date','day','timestamp','time','datetime'].includes(h));
  const pref=['adjclose','adjustedclose','close','closeprice','last','price'];
  const closeName=pref.find(p=>header.includes(p));
  if(dateCol<0||!closeName)throw new Error('Could not find a Date column and a Close (or Adj Close, Price) column in the header row.');
  const closeCol=header.indexOf(closeName),rows=[];let skipped=0;
  for(const line of lines.slice(1,MAX_ROWS+1)){
   const cells=splitLine(line),date=parseDate(cells[dateCol]||''),close=parseNumber(cells[closeCol]??'');
   if(!date||!Number.isFinite(close)||close<=0){skipped++;continue;}
   rows.push({date,close});
  }
  rows.sort((a,b)=>a.date.localeCompare(b.date));
  for(let i=1;i<rows.length;i++)if(rows[i].date===rows[i-1].date)throw new Error(`The date ${rows[i].date} appears more than once. Use one row per trading day.`);
  if(rows.length<2)throw new Error('Fewer than two rows had a valid date and a positive price.');
  return {rows,column:closeName==='adjclose'||closeName==='adjustedclose'?'Adj Close':closeName==='close'||closeName==='closeprice'?'Close':'Price',
          skipped,truncated:lines.length-1>MAX_ROWS};
 }

 function sma(values,n){return values.map((_,i)=>i+1<n?null:values.slice(i+1-n,i+1).reduce((a,b)=>a+b,0)/n);}
 function rsi(values,n=14){
  const out=values.map(()=>null);if(values.length<=n)return out;
  let gain=0,loss=0;
  for(let i=1;i<=n;i++){const d=values[i]-values[i-1];if(d>0)gain+=d;else loss-=d;}
  gain/=n;loss/=n;out[n]=loss===0?100:100-100/(1+gain/loss);
  for(let i=n+1;i<values.length;i++){
   const d=values[i]-values[i-1];gain=(gain*(n-1)+Math.max(d,0))/n;loss=(loss*(n-1)+Math.max(-d,0))/n;
   out[i]=loss===0?100:100-100/(1+gain/loss);
  }
  return out;
 }
 function stats(rows){
  const v=rows.map(r=>r.close),first=rows[0],last=rows[rows.length-1];
  const years=(Date.parse(last.date)-Date.parse(first.date))/DAY/365.25;
  const logs=v.slice(1).map((x,i)=>Math.log(x/v[i]));
  const mean=logs.reduce((a,b)=>a+b,0)/logs.length;
  const sd=logs.length>1?Math.sqrt(logs.reduce((a,b)=>a+(b-mean)**2,0)/(logs.length-1)):null;
  let peak=rows[0],dd={value:0,peak:rows[0].date,trough:rows[0].date};
  for(const r of rows){if(r.close>peak.close)peak=r;const x=r.close/peak.close-1;if(x<dd.value)dd={value:x,peak:peak.date,trough:r.date};}
  const latestRsi=rsi(v).at(-1);
  return {start:first.date,end:last.date,sessions:rows.length,first:first.close,last:last.close,total_return:last.close/first.close-1,
          cagr:years>=1?(last.close/first.close)**(1/years)-1:null,volatility:sd===null?null:sd*Math.sqrt(TRADING_DAYS),
          max_drawdown:dd,rsi:latestRsi};
 }
 // Growth of a starting amount on the dates every series shares.
 function growth(seriesList,amount=10000){
  if(!seriesList.length)return {dates:[],lines:[]};
  const maps=seriesList.map(s=>new Map(s.rows.map(r=>[r.date,r.close])));
  const dates=seriesList[0].rows.map(r=>r.date).filter(d=>maps.every(m=>m.has(d)));
  return {dates,lines:seriesList.map((s,i)=>({name:s.name,values:dates.map(d=>amount*maps[i].get(d)/maps[i].get(dates[0]))}))};
 }
 function simulate(rows,{amount,start,mode='lump'}){
  if(!(amount>0)||!Number.isFinite(amount))throw new Error('Enter an amount greater than zero.');
  const from=rows.findIndex(r=>r.date>=start);
  if(from<0)throw new Error('The start date is after the last row in the file.');
  const buys=[];
  if(mode==='lump')buys.push(rows[from]);
  else{let month='';for(const r of rows.slice(from)){const m=r.date.slice(0,7);if(m!==month){buys.push(r);month=m;}}}
  const shares=buys.reduce((s,r)=>s+amount/r.close,0),invested=amount*buys.length,last=rows[rows.length-1];
  return {buys:buys.length,first_buy:buys[0].date,invested,shares,value:shares*last.close,end:last.date,
          gain:shares*last.close-invested,percent:shares*last.close/invested-1};
 }
 const RULES={close_above:'Close above',close_below:'Close below',rsi_above:'RSI(14) above',rsi_below:'RSI(14) below'};
 function checkRule(rows,rule){
  const latest=rule.type.startsWith('rsi')?rsi(rows.map(r=>r.close)).at(-1):rows[rows.length-1].close;
  if(latest===null||!Number.isFinite(rule.value))return {latest:null,triggered:false};
  return {latest,triggered:rule.type.endsWith('above')?latest>rule.value:latest<rule.value};
 }
 // Clearly fictional sample so visitors can try the tools before supplying a file.
 function example(name,seed,drift){
  const rows=[];let price=100,t=Date.UTC(2021,0,4),s=seed;
  const rand=()=>{s=(s*1103515245+12345)%2147483648;return s/2147483648;};
  while(rows.length<1260){const d=new Date(t).getUTCDay();if(d&&d<6){price*=Math.exp(drift/TRADING_DAYS+0.018*(rand()+rand()+rand()-1.5));rows.push({date:new Date(t).toISOString().slice(0,10),close:+price.toFixed(2)});}t+=DAY;}
  return {name,rows,column:'Fictional',fictional:true};
 }
 const api={parseCsv,parseDate,sma,rsi,stats,growth,simulate,checkRule,RULES,example};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PriceLab=api;
})(typeof globalThis!=='undefined'?globalThis:this);
