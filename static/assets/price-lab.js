'use strict';
(()=>{
 const L=window.PriceLab,$=id=>document.getElementById(id),SVG='http://www.w3.org/2000/svg';
 const RULES_KEY='research-desk.price-lab.rules.v1',MAX_SERIES=4,COLORS=['#7fa9f0','#e8b66b','#8fd9a8','#e98a8a'];
 let series=[],rules={};
 try{const r=JSON.parse(localStorage.getItem(RULES_KEY)||'{}');if(r&&typeof r==='object')rules=r;}catch{}
 const saveRules=()=>{try{localStorage.setItem(RULES_KEY,JSON.stringify(rules));}catch{$('rule-status').textContent='Browser storage is unavailable, so rules last only until you close this tab.';}};

 function el(tag,attrs={},text){const n=document.createElement(tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
 function svg(tag,attrs={},text){const n=document.createElementNS(SVG,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
 const pct=v=>v===null||v===undefined?'—':`${v<0?'−':''}${Math.abs(v*100).toFixed(1)}%`;
 const usd=v=>`${v<0?'−':''}$${Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
 const num=v=>v>=1000?v.toLocaleString('en-US',{maximumFractionDigits:0}):v.toFixed(2);

 function lineChart(root,dates,lines,format){
  root.replaceChildren();
  const W=640,H=260,L0=56,R0=10,T=12,B=26,all=lines.flatMap(l=>l.values.filter(v=>v!==null));
  if(dates.length<2||!all.length){root.append(el('p',{},'Not enough shared dates to draw this chart.'));return;}
  let min=Math.min(...all),max=Math.max(...all);const pad=(max-min)*.06||max*.05;min-=pad;max+=pad;
  const x=i=>L0+i*(W-L0-R0)/(dates.length-1),y=v=>T+(max-v)/(max-min)*(H-T-B);
  const chart=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'presentation'});
  for(let k=0;k<=4;k++){const v=min+(max-min)*k/4;chart.append(svg('line',{class:'grid',x1:L0,x2:W-R0,y1:y(v),y2:y(v)}),svg('text',{x:L0-6,y:y(v)+4,'text-anchor':'end'},format(v)));}
  [0,Math.floor((dates.length-1)/2),dates.length-1].forEach(i=>chart.append(svg('text',{x:x(i),y:H-8,'text-anchor':i===0?'start':i===dates.length-1?'end':'middle'},dates[i])));
  lines.forEach(line=>{
   let d='';line.values.forEach((v,i)=>{if(v===null)return;d+=`${d&&line.values[i-1]!==null?'L':'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;});
   chart.append(svg('path',{d,fill:'none',stroke:line.color,'stroke-width':line.width||2,'stroke-dasharray':line.dash||'','stroke-linejoin':'round'}));
  });
  root.append(chart);
 }
 function fillSelect(select,keep=true){
  const current=select.value;select.replaceChildren();
  series.forEach((s,i)=>select.append(el('option',{value:String(i)},s.name)));
  if(keep&&[...select.options].some(o=>o.value===current))select.value=current;
 }

 function renderAll(){
  ['chart-series','sim-series','rule-series'].forEach(id=>fillSelect($(id)));
  const list=$('series-list');list.replaceChildren();
  series.forEach((s,i)=>{
   const li=el('li');li.append(el('span',{class:'form'},s.fictional?'EXAMPLE':'CSV'),el('strong',{},s.name),
    el('time',{},`${s.rows[0].date} to ${s.rows.at(-1).date}`),el('span',{class:'meta'},`${s.rows.length.toLocaleString('en-US')} rows · ${s.column}${s.skipped?` · ${s.skipped} rows skipped`:''}${s.truncated?' · only the first 20,000 rows read':''}`));
   const remove=el('button',{type:'button','aria-label':`Remove ${s.name}`},'Remove');remove.onclick=()=>{series.splice(i,1);renderAll();};
   li.append(remove);list.append(li);
  });
  $('file-status').textContent=series.length?`${series.length} of ${MAX_SERIES} files open.`:'No files open yet.';
  if(series.length&&!$('sim-start').value)$('sim-start').value=series[0].rows[Math.max(0,series[0].rows.length-253)].date;
  renderChart();renderStats();renderGrowth();renderRules();
 }
 function renderChart(){
  const s=series[+$('chart-series').value],root=$('price-chart');
  if(!s){root.replaceChildren(el('p',{},'Open a file or try the example to see a chart.'));$('price-caption').textContent='';return;}
  const n=+$('chart-range').value,closes=s.rows.map(r=>r.close),start=n?Math.max(0,s.rows.length-n):0;
  const slice=a=>a.slice(start),lines=[{values:slice(closes),color:COLORS[0]}];
  if($('show-sma20').checked)lines.push({values:slice(L.sma(closes,20)),color:COLORS[1],width:1.5});
  if($('show-sma50').checked)lines.push({values:slice(L.sma(closes,50)),color:COLORS[2],width:1.5,dash:'5 3'});
  lineChart(root,slice(s.rows.map(r=>r.date)),lines,num);
  const st=L.stats(s.rows);
  root.setAttribute('aria-label',`${s.name} price from ${s.rows[start].date} to ${st.end}, last ${num(st.last)}.`);
  $('price-caption').textContent=`${s.name}${s.fictional?' (fictional)':''} · ${s.column} from your file · blue: price, amber: 20-day average, green dashed: 50-day average.`;
 }
 function renderStats(){
  const body=$('stats-table').tBodies[0];body.replaceChildren();
  series.forEach(s=>{const st=L.stats(s.rows),tr=el('tr');
   tr.append(el('td',{},s.name),el('td',{},`${st.start} to ${st.end}`),el('td',{class:'num'},pct(st.total_return)),el('td',{class:'num'},pct(st.cagr)),
    el('td',{class:'num'},pct(st.volatility)),el('td',{class:'num',title:`${st.max_drawdown.peak} to ${st.max_drawdown.trough}`},pct(st.max_drawdown.value)),el('td',{class:'num'},st.rsi===null?'—':st.rsi.toFixed(0)));
   body.append(tr);});
  if(!series.length){const tr=el('tr');tr.append(el('td',{colspan:'7'},'No files open.'));body.append(tr);}
 }
 function renderGrowth(){
  const root=$('growth-chart'),legend=$('growth-legend');legend.replaceChildren();
  if(series.length<2){root.replaceChildren(el('p',{},'Open two or more files to compare them.'));return;}
  const g=L.growth(series);
  lineChart(root,g.dates,g.lines.map((l,i)=>({values:l.values,color:COLORS[i]})),v=>`$${(v/1000).toFixed(1)}k`);
  g.lines.forEach((l,i)=>{const item=el('span',{class:'legend-item'});const swatch=el('span',{class:`swatch swatch-${i}`,'aria-hidden':'true'});item.append(swatch,` ${l.name}: ${l.values.length?usd(l.values.at(-1)):'—'}`);legend.append(item);});
  if(g.dates.length)legend.append(el('span',{class:'meta'},`${g.dates[0]} to ${g.dates.at(-1)}, ${g.dates.length.toLocaleString('en-US')} shared dates.`));
 }
 function renderRules(){
  const list=$('rule-list');list.replaceChildren();let count=0;
  series.forEach(s=>(rules[s.name]||[]).forEach((rule,i)=>{
   count++;const r=L.checkRule(s.rows,rule),li=el('li');
   li.append(el('span',{class:r.triggered?'badge':'form'},r.triggered?'MET':'NOT MET'),el('strong',{},s.name),
    el('span',{},`${L.RULES[rule.type]} ${num(rule.value)} · latest ${r.latest===null?'not enough data':num(r.latest)} on ${s.rows.at(-1).date}`));
   const remove=el('button',{type:'button','aria-label':'Remove rule'},'Remove');remove.onclick=()=>{rules[s.name].splice(i,1);if(!rules[s.name].length)delete rules[s.name];saveRules();renderRules();};
   li.append(remove);list.append(li);
  }));
  if(!count)list.append(el('li',{class:'empty'},series.length?'No rules for the open files yet.':'Open a file to add rules.'));
 }

 async function readFiles(files){
  const status=$('file-status'),errors=[];
  for(const file of files){
   if(series.length>=MAX_SERIES){errors.push(`Only ${MAX_SERIES} files can be open at once.`);break;}
   if(file.size>5e6){errors.push(`${file.name} is larger than 5 MB.`);continue;}
   try{const parsed=L.parseCsv(await file.text());const name=file.name.replace(/\.(csv|txt)$/i,'');
    series=series.filter(s=>s.name!==name);series.push({name,...parsed});}
   catch(error){errors.push(`${file.name}: ${error.message}`);}
  }
  renderAll();if(errors.length)status.textContent=errors.join(' ');
 }

 $('price-files').onchange=e=>{readFiles([...e.target.files]);e.target.value='';};
 $('load-example').onclick=()=>{series=series.filter(s=>!s.fictional);
  [['Fictional Fund A',11,.12],['Fictional Fund B',29,.04]].forEach(([n,seed,drift])=>{if(series.length<MAX_SERIES)series.push(L.example(n,seed,drift));});renderAll();};
 $('clear-files').onclick=()=>{series=[];renderAll();};
 ['chart-series','chart-range','show-sma20','show-sma50'].forEach(id=>$(id).onchange=renderChart);
 Object.entries(L.RULES).forEach(([k,v])=>$('rule-type').append(el('option',{value:k},v)));
 $('sim-form').onsubmit=e=>{e.preventDefault();const s=series[+$('sim-series').value],out=$('sim-results');out.replaceChildren();
  if(!s){$('sim-status').textContent='Open a file first.';return;}
  try{const r=L.simulate(s.rows,{amount:Number($('sim-amount').value),start:$('sim-start').value||s.rows[0].date,mode:$('sim-mode').value});
   [['Invested',usd(r.invested)],['Value on '+r.end,usd(r.value)],['Gain or loss',`${usd(r.gain)} (${pct(r.percent)})`],['Purchases',`${r.buys} from ${r.first_buy}`]].forEach(([k,v])=>{const d=el('div');d.append(el('dt',{},k),el('dd',{},v));out.append(d);});
   $('sim-status').textContent=`Hypothetical result for ${s.name}${s.fictional?' (fictional data)':''}. No trade was placed.`;}
  catch(error){$('sim-status').textContent=error.message;}};
 $('rule-form').onsubmit=e=>{e.preventDefault();const s=series[+$('rule-series').value],value=Number($('rule-value').value);
  if(!s){$('rule-status').textContent='Open a file first.';return;}
  if(!$('rule-value').value||!Number.isFinite(value)){$('rule-status').textContent='Enter a number for the rule.';return;}
  (rules[s.name]=rules[s.name]||[]).push({type:$('rule-type').value,value});saveRules();$('rule-value').value='';$('rule-status').textContent=`Added a rule for ${s.name}.`;renderRules();};
 document.querySelectorAll('nav a').forEach(a=>{if(new URL(a.href).pathname===location.pathname)a.setAttribute('aria-current','page');});
 renderAll();
})();
