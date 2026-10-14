"use strict";
(() => {
 const find=id=>document.getElementById(id);if(!find('research-panel'))return;
 let assets=[],revision=0,busy=false,signedIn=false,mode='sample';
 const picker=find('research-asset'),kind=find('research-kind'),days=find('research-days'),status=find('research-status'),results=find('research-results');
 function invalidate(){revision++;results.replaceChildren();}
 function controls(){find('research-load').disabled=busy||!signedIn||mode==='not_enabled';find('research-run').disabled=busy||!signedIn||!picker.value;find('research-save').disabled=busy||!signedIn||!picker.value||kind.value==='crypto';}
 function filter(){const previous=picker.value,term=find('research-search').value.trim().toLowerCase(),exchange=find('research-exchange').value;
  const matched=assets.filter(a=>(!exchange||a.exchange===exchange)&&`${a.name} ${a.symbol} ${a.exchange}`.toLowerCase().includes(term));
  picker.replaceChildren();const prompt=el('option',matched.length?'Choose an asset':'Load listings or refine your filters');prompt.value='';picker.append(prompt);
  for(const a of matched){const option=el('option',`${a.name} (${a.symbol}) · ${a.exchange}`);option.value=a.id;picker.append(option);}
  picker.value=matched.some(a=>a.id===previous)?previous:'';find('research-matches').textContent=`${matched.length} of ${assets.length} listings. Search and exchange filters use the loaded list without more requests.`;controls();
 }
 document.addEventListener('account-session',event=>{signedIn=event.detail.signedIn;mode=event.detail.mode;if(!signedIn){assets=[];find('research-search').value='';find('research-exchange').value='';invalidate();filter();}controls();});
 kind.addEventListener('change',()=>{assets=[];invalidate();find('research-exchange').value='';find('research-exchange').disabled=kind.value==='crypto';days.replaceChildren();const entries=kind.value==='crypto'?[['90','3 months'],['180','6 months'],['364','Last year (364 completed days)']]:[['90','3 months'],['365','1 year'],['1827','5 years'],['3653','10 years']];for(const [value,text]of entries){const option=el('option',text);option.value=value;days.append(option);}days.value=kind.value==='crypto'?'90':'3653';filter();status.textContent='Load this market’s listings to begin.';});
 for(const [id,event]of [['research-search','input'],['research-exchange','change']])find(id).addEventListener(event,()=>{invalidate();filter();});
 picker.addEventListener('change',()=>{invalidate();controls();});days.addEventListener('change',invalidate);
 async function api(url){const response=await fetch(url,{credentials:'same-origin'});const body=await response.json();if(!response.ok){if(response.status===401){signedIn=false;assets=[];invalidate();filter();document.dispatchEvent(new CustomEvent('account-session-expired'));}throw Error(body.error?.message||'Research is unavailable. Retry manually.');}return body;}
 find('research-load').addEventListener('click',async()=>{if(busy||!signedIn)return;invalidate();const current=revision;busy=true;controls();status.textContent='Loading market listings…';try{const data=await api(`/v2/research/assets?kind=${encodeURIComponent(kind.value)}`);if(current!==revision||!signedIn)return;assets=[...data.assets].sort((a,b)=>a.name.localeCompare(b.name)||a.symbol.localeCompare(b.symbol)||a.exchange.localeCompare(b.exchange));filter();status.textContent=`Listings ready${data.stale?' · cached catalog':''}. Choose an asset and history window.`;}catch(error){if(current===revision)status.textContent=error.message;}finally{busy=false;controls();}});
 function draw(data){
  const first=data.history[0],last=data.history.at(-1);if(!last){throw Error('No completed prices were returned.');}
  results.append(el('h3',data.asset.name),el('p',data.data_mode==='sample'?'Synthetic sample prices · demonstration only':'Provider history · historical prices, not a live quote'));
  const cards=el('div');cards.className='research-summary';const price=el('article'),change=el('article'),returnPct=(last.price/first.price-1)*100;
  const value=el('p',priceLabel(last.price));value.className='research-price';price.append(el('h3','Latest available observation'),value,el('p',`${last.date} · USD`));
  const ret=el('p',`${returnPct>0?'+':''}${returnPct.toFixed(2)}%`);ret.className='research-return';change.append(el('h3','Change in loaded history'),ret,el('p',`${first.date} to ${last.date}${data.asset.asset_class==='crypto'?'':' · excludes dividends'}`));cards.append(price,change);results.append(cards);
  priceChart(results,data.history,{sessions:data.asset.asset_class!=='crypto',bars:data.bars});
  const indicators=data.indicators;
  if(indicators){const explanations=el('div');explanations.className='research-signals';for(const [label,text]of [['Trend',`The latest price is ${last.price>indicators.ma_25?'above':last.price<indicators.ma_25?'below':'at'} its 25-observation average. This describes history, not a forecast.`],['Momentum',`RSI is ${format(indicators.rsi_14)} out of 100. The usual 30/70 thresholds do not guarantee a reversal.`],['MACD',`Its histogram is ${format(indicators.macd_histogram)} USD: the difference between MACD and its signal line, not an accuracy percentage.`]]){const card=el('article');card.append(el('h3',label),el('p',text));explanations.append(card);}results.append(explanations);
   const exact=el('details'),table=el('table');exact.className='chart-table';exact.append(el('summary','Exact indicator values'));for(const [key,value]of Object.entries(indicators)){const row=el('tr');row.append(el('th',key.replaceAll('_',' ')),el('td',format(value)));table.append(row);}exact.append(table);results.append(exact);
  }else results.append(el('p','Indicators are unavailable when history is too short or has gaps. No values were invented.'));
  const coverage=el('details');coverage.append(el('summary','Data coverage and limitations'),el('p',`${data.window.observations} observations · ${data.window.missing_sessions.length} missing dates.`));for(const text of data.limitations)coverage.append(el('p',text));if(data.window.missing_sessions.length)coverage.append(el('p',data.window.missing_sessions.join(', ')));results.append(coverage);
 }
 find('research-form').addEventListener('submit',async event=>{event.preventDefault();if(busy||!signedIn||!picker.value)return;invalidate();const current=revision;busy=true;controls();status.textContent='Loading completed historical observations…';try{const data=await api(`/v2/research/analysis?kind=${encodeURIComponent(kind.value)}&asset_id=${encodeURIComponent(picker.value)}&days=${encodeURIComponent(days.value)}`);if(current!==revision||!signedIn)return;draw(data);status.textContent='Analysis ready. Zoom and chart controls use already-loaded data.';}catch(error){if(current===revision){results.replaceChildren();status.textContent=error.message;}}finally{busy=false;controls();}});
 find('research-save').addEventListener('click',()=>{const asset=assets.find(a=>a.id===picker.value);if(!signedIn||!asset||asset.asset_class==='crypto')return;document.dispatchEvent(new CustomEvent('account-save-listing',{detail:{id:asset.id,name:asset.name}}));});
 controls();
})();
