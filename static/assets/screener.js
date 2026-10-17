"use strict";
(() => {
 const selected=[],rows=[],feed=ScreeningFeed.selectedHistory(request);
 const status=$('screen-status'),output=$('screen-results'),period=$('screen-period');let busy=false,generation=0;
 const periodName=()=>({'ytd':'YTD','1m':'1 month','6m':'6 months','1y':'1 year'}[period?.value||'ytd']);
 const changed=()=>{generation++;rows.length=0;output.replaceChildren();status.textContent='Comparison changed. Refresh explicitly to load matching history.';render();};
 function render(){
  $('screen-list').replaceChildren();
  for(const a of selected){const row=el('li',a.name),remove=el('button','Remove');remove.type='button';remove.disabled=busy;remove.addEventListener('click',()=>{selected.splice(selected.indexOf(a),1);changed();});row.append(remove);$('screen-list').append(row);}
  const value=id=>$(id)?.value?.trim()||'',number=id=>{const raw=value(id);return raw===''?null:Number(raw);};
  const min=number('screen-min-price'),max=number('screen-max-price'),ret=number('screen-min-return'),volume=number('screen-min-volume'),kind=value('screen-kind');
  output.replaceChildren();
  if([min,max,ret,volume].some(n=>n!==null&&!Number.isFinite(n))||(min!==null&&min<0)||(max!==null&&max<0)||(volume!==null&&volume<0)||(min!==null&&max!==null&&min>max)){output.append(el('p','Check result filters: use valid numbers and a minimum price no higher than the maximum.'));return;}
  const order=$('screen-order').value,metric=['ytd_return','worst_ytd'].includes(order)?'return_fraction':order;
  const available=rows.filter(r=>!r.unavailable),ranked=available.filter(r=>(!kind||r.asset_class===kind)&&(min===null||r.price>=min)&&(max===null||r.price<=max)&&(ret===null||r.return_fraction*100>=ret)&&(volume===null||r.average_volume>=volume)).sort((a,b)=>(order==='worst_ytd'?a[metric]-b[metric]:b[metric]-a[metric])||a.name.localeCompare(b.name));
  for(const [i,row]of ranked.entries()){const card=el('article');card.className='comparison-result';const gain=el('p',`${row.return_fraction>=0?'+':''}${(row.return_fraction*100).toFixed(2)}%`);gain.className=row.return_fraction<0?'return-negative comparison-return':'return-positive comparison-return';card.append(el('h3',`${i+1}. ${row.name}`),gain,el('p',`${periodName()} price return · ${row.start} to ${row.as_of}`),el('p',`Close ${priceLabel(row.price)} · average daily volume ${format(row.average_volume)} shares`));const source=el('details');source.append(el('summary','Source and coverage'),el('p',`${researchSourceLabel()} · retrieved ${row.fetched_at_utc||'time unavailable'}${row.cache_hit?' (cached)':''}. Average volume excludes the baseline session. Price returns exclude dividends, fees and taxes.`));card.append(source);output.append(card);}
  if(available.length)output.append(el('p',`Showing ${ranked.length} of ${available.length} available selected results. Filters and ranking apply only to this comparison list, not the whole market.`));
  for(const row of rows.filter(r=>r.unavailable))output.append(el('p',`${row.name}: ${row.unavailable}`));
 }
 $('screen-add').addEventListener('click',()=>{if(busy)return;const select=$('stock-options'),id=select.value;if(!id){status.textContent='Choose a listing above first.';return;}if(selected.some(a=>a.id===id))return;if(selected.length===5){status.textContent='Compare up to five listings at once to limit free-tier requests.';return;}const option=Array.from(select.options).find(o=>o.value===id);if(!option)return;selected.push({id,name:option.textContent});changed();});
 $('screen-order').addEventListener('change',render);
 for(const id of ['screen-kind','screen-min-price','screen-max-price','screen-min-return','screen-min-volume'])$(id)?.addEventListener('input',render);
 $('screen-clear-filters')?.addEventListener('click',()=>{for(const id of ['screen-kind','screen-min-price','screen-max-price','screen-min-return','screen-min-volume'])if($(id))$(id).value='';render();});
 $('screen-filter-toggle')?.addEventListener('click',()=>{const panel=$('screen-filters'),open=panel.hidden;panel.hidden=!open;$('screen-filter-toggle').setAttribute('aria-expanded',String(open));});
 period?.addEventListener('change',changed);
 $('screen-run').addEventListener('click',async()=>{
  if(busy||!selected.length)return;busy=true;const revision=++generation;$('screen-run').disabled=true;$('screen-add').disabled=true;if(period)period.disabled=true;rows.length=0;render();
  status.textContent=`Loading ${periodName()} comparison for ${selected.length} selected listings. Requests run one at a time; no retries.`;
  try{const result=await feed.screen({listings:selected.map(a=>({...a})),period:period?.value||'ytd',isCurrent:()=>generation===revision,onRow:row=>{if(generation!==revision)return;rows.push(row);render();}});if(result.cancelled||generation!==revision)return;status.textContent=result.complete?`Compared ${rows.length} selected listings. This is not a whole-market ranking. Price returns exclude dividends.`:'Comparison stopped after a data error to avoid further requests. Available results are partial.';}
  catch(error){if(generation===revision)status.textContent=error.message;}
  finally{busy=false;$('screen-run').disabled=false;$('screen-add').disabled=false;if(period)period.disabled=false;render();}
 });
})();
