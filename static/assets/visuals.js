"use strict";
// Local SVG rendering: no external chart service or data transfer.
function visualSummary(parent, e) {
 const cards = el("div"); cards.className = "summary-cards";
 const extra = el("details"), extraCards=el("div");extraCards.className="summary-cards";extra.append(el("summary","More signals and strategy context"),extraCards);
 const add = (title, text) => { const card = el("article"); card.append(el("h3", title), el("p", text)); (title.startsWith("Price range") || title.startsWith("Past turning") || title === "Strategy evidence" ? extraCards : cards).append(card); };
 const i = e.indicators, b = e.backtest;
 const hasBands = Number.isFinite(i.bollinger_lower) && Number.isFinite(i.bollinger_upper);
 const bandPosition = i.latest_history_price_usd > i.bollinger_upper ? "above" : i.latest_history_price_usd < i.bollinger_lower ? "below" : "within";
 add("Price range · Bollinger Bands", hasBands ? `Price is ${bandPosition} the bands around its 20-observation average. The bands describe recent price variation; they are not a forecast range or a guarantee that price will reverse.` : "Not enough data to describe the recent price range.");
 const swings = [...(Array.isArray(i.support) ? i.support : []), ...(Array.isArray(i.resistance) ? i.resistance : [])];
 add("Past turning points · support / resistance", swings.length ? "These mark earlier swing lows and highs. Price may already have crossed them, so support is not necessarily below today's price and resistance is not necessarily above it. They are not guaranteed floors or ceilings." : "No confirmed swing levels are available in this window. This does not mean the price has no risk.");
 add("Price trend", Number.isFinite(i.ma_25) ? `Historical price is ${i.latest_history_price_usd > i.ma_25 ? "above" : i.latest_history_price_usd < i.ma_25 ? "below" : "equal to"} its 25-observation average. This describes recent prices, not what happens next.` : "Not enough data to compare the price with its recent average.");
 add("Price momentum · RSI", Number.isFinite(i.rsi_14) ? `RSI is ${i.rsi_14.toFixed(1)} out of 100. ${i.rsi_14 >= 70 ? "Recent gains are unusually strong (often called overbought). That does not predict a reversal." : i.rsi_14 <= 30 ? "Recent losses are unusually strong (often called oversold). That does not guarantee a rebound." : "It is between the conventional 30 and 70 thresholds; this alone is not a buy or sell signal."}` : "RSI is unavailable.");
 add("Momentum comparison · MACD", Number.isFinite(i.macd_histogram) ? `MACD is ${i.macd_histogram > 0 ? "above" : i.macd_histogram < 0 ? "below" : "equal to"} its signal line. This compares smoothed price trends; it does not establish a fresh crossover or predict returns.` : "MACD is unavailable.");
 add("Strategy evidence", b.closed_trades === 0 ? "No completed trades in this window, so this backtest cannot estimate a win rate." : `${b.closed_trades} completed trades. ${b.closed_trades < 5 ? "This is a small sample." : "Past results do not predict future results."} Fees, slippage and open-position profit/loss are excluded.`);
 parent.append(cards,extra);
 parent.append(el("p", `${e.window.observations} daily observations · ${e.window.missing_days} missing days. The current UTC day may be incomplete. These summaries describe indicators, not trading recommendations.`));
}
// One local chart window; gestures never fetch or interpolate provider data.
class ChartWindow {
 constructor(length) {this.length=length;this.first=0;this.last=length-1;}
 set(first,last) {const count=Math.max(1,Math.min(this.length,Math.round(last-first+1)));this.first=Math.max(0,Math.min(this.length-count,Math.round(first)));this.last=this.first+count-1;}
 pan(steps) {this.set(this.first+steps,this.last+steps);}
 zoom(factor,anchor=.5) {const count=this.last-this.first+1,target=Math.max(Math.min(2,this.length),Math.min(this.length,Math.round(count*factor)));const focus=this.first+(count-1)*anchor;this.set(focus-(target-1)*anchor,focus+(target-1)*(1-anchor));}
}
function priceChart(parent, points, options = {}) {
 if(!Array.isArray(points)||points.length<2)return;
 const synthetic=typeof demoWorkspace==='function'&&demoWorkspace();
 const keys=['price','ma_7','ma_25','bollinger_lower','bollinger_middle','bollinger_upper'];
 let previous=-Infinity;
 for(const point of points){const time=Date.parse(point.date+'T00:00:00Z');if(!/^\d{4}-\d{2}-\d{2}$/.test(point.date)||!Number.isFinite(time)||time<=previous||!Number.isFinite(point.price)||point.price<=0||keys.some(key=>point[key]!==null&&!Number.isFinite(point[key])))throw Error('Invalid chart data');previous=time;}
 const timestamps=points.map(p=>Date.parse(p.date)),timesByDate=new Map(points.map((p,i)=>[p.date,timestamps[i]]));
 const bars=options.bars;
 const hasBars=Array.isArray(bars)&&bars.length===points.length&&bars.every((bar,i)=>bar.date===points[i].date&&bar.close===points[i].price&&['open','high','low','close'].every(k=>Number.isFinite(bar[k])&&bar[k]>0)&&bar.low<=Math.min(bar.open,bar.close)&&bar.high>=Math.max(bar.open,bar.close));
 const hasVolume=hasBars&&bars.every(bar=>Number.isFinite(bar.volume)&&bar.volume>=0);
 const view=new ChartWindow(points.length);
 let selectedIndex=points.length-1,expanded=false,svg,marker,crossV,crossH,scaleX,scaleY,gesture=null,pinch=null;
 const pointers=new Map();
 const section=el('section');section.className='price-chart';section.setAttribute('tabindex','-1');
 section.append(el('h3',options.title||(typeof demoWorkspace==='function'&&demoWorkspace()?'Synthetic price history · USD':'Price history · USD')));
 const selected=el('p');selected.className='chart-selected';selected.setAttribute('aria-live','polite');
 const navigation=el('div');navigation.className='chart-navigation';const extraNavigation=el('div');extraNavigation.className='chart-navigation chart-navigation-extra';
 const button=(text,advanced=false)=>{const node=el('button',text);node.type='button';node.className='secondary';(advanced?extraNavigation:navigation).append(node);return node;};
 const back=button('← Previous',true),next=button('Next →',true),latest=button('Latest',true),reset=button('Reset view',true),full=button('Fullscreen');
 const select=(label,entries,advanced=false)=>{const wrapper=el('label',label),node=el('select');for(const [value,text] of entries){const option=el('option',text);option.value=value;node.append(option);}node.value=entries[0][0];wrapper.append(node);(advanced?extraNavigation:navigation).append(wrapper);return node;};
 const range=select('Show',[['all','Full history'],['30','Last month'],['90','Last 3 months'],['365','Last year'],['custom','Custom view']]);
 const style=hasBars?select('Chart type',[['line','Line'],['candles','Candlesticks']]):null;
 const axis=select('Scale',[['linear','Linear'],['log','Logarithmic']]);
 const plot=el('div');plot.className='chart-plot';plot.setAttribute('tabindex','0');plot.setAttribute('role','group');plot.setAttribute('aria-label','Interactive price chart. Arrow keys select dates; plus and minus zoom. Drag to pan, scroll or pinch to zoom.');
 const tooltip=el('p');tooltip.className='chart-tooltip';tooltip.hidden=true;
 const drawing=el('div');plot.append(drawing,tooltip);
 const volumePlot=el('div');volumePlot.className='chart-volume';
 const sliderLabel=el('label','Explore dates'),slider=el('input');slider.type='range';slider.step='1';slider.value=String(selectedIndex);sliderLabel.append(slider);
 const help=el('p','Drag to browse · scroll or pinch to zoom · tap a point for its price.');
 const candleDetails=el('p');candleDetails.className='chart-candle-details';
 const candleGuide=el('p','Each candle shows one trading day. Body: open to close; wick: low to high. Green: close at or above open. Red: close below open.');candleGuide.className='chart-help';help.className='chart-help';
 const status=el('p');status.className='chart-note';status.setAttribute('role','status');
 const controls=el('div');controls.className='chart-controls';
 const toggle=text=>{const label=el('label'),input=el('input');input.type='checkbox';input.checked=false;label.append(input,el('span',text));controls.append(label);return input;};
 const averages=toggle('Moving averages (7 / 25)'),bands=toggle('Bollinger Bands (20)'),volume=hasVolume?toggle('Daily share volume'):null;
 const readout=el('p');readout.className='chart-readout';
 const node=(tag,attrs={},text)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value]of Object.entries(attrs))n.setAttribute(key,String(value));if(text!==undefined)n.textContent=text;return n;};
 const colors={price:'#7db1ff',ma_7:'#5ee0d2',ma_25:'#f4bb78',bollinger_lower:'#bd9fe8',bollinger_middle:'#bd9fe8',bollinger_upper:'#bd9fe8'};
 function inspect(index,announce=true) {
  index=Math.max(view.first,Math.min(view.last,index));const p=points[index];
  marker.setAttribute('cx',scaleX(p));marker.setAttribute('cy',scaleY(p.price));
  crossV.setAttribute('x1',scaleX(p));crossV.setAttribute('x2',scaleX(p));crossH.setAttribute('y1',scaleY(p.price));crossH.setAttribute('y2',scaleY(p.price));
  tooltip.textContent=`${p.date} · ${priceLabel(p.price)}`;
  const candleMode=hasBars&&style?.value==='candles';candleDetails.hidden=!candleMode;candleGuide.hidden=!candleMode;
  if(candleMode){const b=bars[index];const text=`${p.date} · Open ${priceLabel(b.open)} · High ${priceLabel(b.high)} · Low ${priceLabel(b.low)} · Close ${priceLabel(b.close)}`;tooltip.textContent=text;candleDetails.textContent=text;}
  if(announce){selectedIndex=index;slider.value=String(index);selected.textContent=`${p.date} ${options.sessions?'exchange close':'UTC sample'} · ${priceLabel(p.price)}`;slider.setAttribute('aria-valuetext',selected.textContent);back.disabled=index<=view.first;next.disabled=index>=view.last;
   readout.textContent=`${p.date} ${options.sessions?'exchange session':'UTC'} · Price $${format(p.price)} · MA7 ${format(p.ma_7)} · MA25 ${format(p.ma_25)} · Bands ${format(p.bollinger_lower)} / ${format(p.bollinger_middle)} / ${format(p.bollinger_upper)}`;
   if(hasBars){const b=bars[index];readout.append(el('span',` · Open ${priceLabel(b.open)} · High ${priceLabel(b.high)} · Low ${priceLabel(b.low)} · Close ${priceLabel(b.close)} · Volume ${format(b.volume)}`));}
  }
 }
 function draw() {
  const visible=points.slice(view.first,view.last+1),shown=['price',...(averages.checked?['ma_7','ma_25']:[]),...(bands.checked?['bollinger_lower','bollinger_middle','bollinger_upper']:[])];
  const values=visible.flatMap(p=>shown.map(k=>p[k]).filter(Number.isFinite));
  if(style?.value==='candles')for(let i=view.first;i<=view.last;i++)values.push(bars[i].low,bars[i].high);
  const minimum=Math.min(...values),maximum=Math.max(...values);let logarithmic=axis.value==='log';
  if(logarithmic&&minimum<=0){logarithmic=false;axis.value='linear';status.textContent='Log scale requires positive values. A selected indicator reaches zero or below, so linear scale is shown.';}
  else status.textContent=logarithmic?'Logarithmic scale: equal vertical steps represent equal percentage changes. Prices are unchanged.':minimum<0?'Negative axis values come from an indicator band, not a negative stock price.':'Linear scale: equal vertical steps represent equal dollar changes.';
  let low=logarithmic?Math.log(minimum):minimum,high=logarithmic?Math.log(maximum):maximum;const pad=(high-low)*.08||(logarithmic?.01:high*.01)||1;
  low=logarithmic?Math.max(Math.log(Number.MIN_VALUE),low-pad):minimum>=0?Math.max(0,low-pad):low-pad;high=Math.min(logarithmic?Math.log(Number.MAX_VALUE):Number.MAX_VALUE,high+pad);
  const transform=value=>logarithmic?Math.log(value):value;
  const start=Date.parse(visible[0].date),end=Date.parse(visible.at(-1).date);
  scaleX=p=>start===end?232.5:65+(timesByDate.get(p.date)-start)/(end-start)*335;scaleY=value=>235-(transform(value)-low)/(high-low)*205;
  svg=node('svg',{viewBox:'0 0 420 280',role:'img','aria-label':`${style?.value==='candles'?(synthetic?'Synthetic daily OHLC candlesticks':'Split-adjusted daily OHLC candlesticks'):(synthetic?'Synthetic USD demonstration values':'Historical USD prices')} from ${visible[0].date} to ${visible.at(-1).date}. Missing data is not filled.`});
  for(let j=0;j<=4;j++){const step=low+(high-low)*j/4,value=logarithmic?Math.exp(step):step,pos=scaleY(value);svg.append(node('line',{x1:65,x2:400,y1:pos,y2:pos,stroke:'#293e5c'}),node('text',{x:57,y:pos+4,'text-anchor':'end',fill:'#aebed4','font-size':12},new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(value)));}
  for(const key of shown){if(key==='price'&&style?.value==='candles')continue;let d='',lastTime=null;for(const p of visible){const time=Date.parse(p.date);if(p[key]===null){lastTime=null;continue;}const move=lastTime===null||(options.sessions?p.break_before===true:time-lastTime>86400000);d+=`${move?'M':'L'}${scaleX(p).toFixed(2)},${scaleY(p[key]).toFixed(2)} `;lastTime=time;}svg.append(node('path',{d,fill:'none',stroke:colors[key],'stroke-width':key==='price'?2.5:1.5,'stroke-dasharray':key.startsWith('bollinger')?'4 4':key==='ma_25'?'8 3':'none'}));}
  if(style?.value==='candles'){
   const distances=visible.slice(1).map((p,i)=>scaleX(p)-scaleX(visible[i]));const width=Math.max(.3,Math.min(10,(distances.length?Math.min(...distances):16)*.65));
   for(let i=view.first;i<=view.last;i++){const b=bars[i],x=scaleX(points[i]),color=b.close>=b.open?'#5ee0b2':'#ff8996';svg.append(node('line',{x1:x,x2:x,y1:scaleY(b.high),y2:scaleY(b.low),stroke:color,'stroke-width':Math.max(.5,width*.2)}),node('rect',{x:x-width/2,y:Math.min(scaleY(b.open),scaleY(b.close)),width,height:Math.max(.6,Math.abs(scaleY(b.open)-scaleY(b.close))),fill:color,'data-candle':b.date}));}
  }
  svg.append(node('text',{x:65,y:265,fill:'#aebed4','font-size':12},visible[0].date),node('text',{x:400,y:265,'text-anchor':'end',fill:'#aebed4','font-size':12},visible.at(-1).date));
  crossV=node('line',{y1:30,y2:235,stroke:'#99b9e0','stroke-dasharray':'3 3'});crossH=node('line',{x1:65,x2:400,stroke:'#99b9e0','stroke-dasharray':'3 3'});marker=node('circle',{r:4,fill:'#fff'});svg.append(crossV,crossH,marker);drawing.replaceChildren(svg);
  slider.min=String(view.first);slider.max=String(view.last);inspect(selectedIndex);
  volumePlot.replaceChildren();volumePlot.hidden=!volume?.checked;
  if(volume?.checked){const max=Math.max(...bars.slice(view.first,view.last+1).map(b=>b.volume))||1,chart=node('svg',{viewBox:'0 0 420 75',role:'img','aria-label':'Daily share volume over the same visible dates'});chart.append(node('text',{x:65,y:12,fill:'#aebed4','font-size':10},'Daily share volume'));for(let i=view.first;i<=view.last;i++){const b=bars[i],height=b.volume/max*48;chart.append(node('rect',{x:scaleX(points[i])-Math.max(.3,Math.min(6,160/visible.length))/2,y:65-height,width:Math.max(.3,Math.min(6,160/visible.length)),height,fill:'#7db1ff'}));}volumePlot.append(chart);}
 }
 function nearest(fraction){const first=timestamps[view.first],last=timestamps[view.last],target=first+Math.max(0,Math.min(1,fraction))*(last-first);let low=view.first,high=view.last;while(low<high){const mid=Math.floor((low+high)/2);if(timestamps[mid]<target)low=mid+1;else high=mid;}return low>view.first&&target-timestamps[low-1]<=timestamps[low]-target?low-1:low;}
 function fraction(event){const rect=svg.getBoundingClientRect();return Math.max(0,Math.min(1,((event.clientX-rect.left)/rect.width*420-65)/335));}
 function hover(event){inspect(nearest(fraction(event)),false);const rect=plot.getBoundingClientRect();tooltip.hidden=false;tooltip.style.left=`${Math.max(0,Math.min(rect.width-170,event.clientX-rect.left+12))}px`;tooltip.style.top=`${Math.max(0,event.clientY-rect.top-45)}px`;}
 plot.addEventListener('pointerdown',event=>{if(event.pointerType==='mouse'&&event.button!==0)return;plot.focus?.();plot.setPointerCapture?.(event.pointerId);pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});gesture={x:event.clientX,y:event.clientY,first:view.first,last:view.last,moved:false};if(pointers.size===2){const [a,b]=[...pointers.values()];pinch={distance:Math.hypot(a.x-b.x,a.y-b.y)||1,first:view.first,last:view.last};}});
 plot.addEventListener('pointermove',event=>{
  if(!pointers.has(event.pointerId)){if(event.pointerType==='mouse')hover(event);return;}
  pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
  if(pointers.size===2&&pinch){const [a,b]=[...pointers.values()],distance=Math.hypot(a.x-b.x,a.y-b.y)||1;view.set(pinch.first,pinch.last);view.zoom(pinch.distance/distance);gesture.moved=true;range.value='custom';draw();return;}
  if(!gesture)return;const delta=event.clientX-gesture.x;if(Math.abs(delta)<5&&!gesture.moved)return;gesture.moved=true;view.set(gesture.first,gesture.last);view.pan(Math.round(-delta/(svg.getBoundingClientRect().width*335/420)*(gesture.last-gesture.first+1)));range.value='custom';draw();tooltip.hidden=true;
 });
 function release(event){if(gesture&&!gesture.moved&&pointers.size===1)inspect(nearest(fraction(event)));pointers.delete(event.pointerId);pinch=null;if(!pointers.size)gesture=null;else{const p=[...pointers.values()][0];gesture={x:p.x,y:p.y,first:view.first,last:view.last,moved:true};}tooltip.hidden=true;}
 plot.addEventListener('pointerup',release);plot.addEventListener('pointercancel',()=>{pointers.clear();gesture=null;pinch=null;tooltip.hidden=true;});
 plot.addEventListener('pointerleave',()=>{if(!pointers.size){tooltip.hidden=true;inspect(selectedIndex);}});
 plot.addEventListener('wheel',event=>{event.preventDefault();const amount=event.deltaMode===1?event.deltaY*16:event.deltaMode===2?event.deltaY*280:event.deltaY;view.zoom(Math.exp(Math.max(-1,Math.min(1,amount*.002))),fraction(event));range.value='custom';tooltip.hidden=true;draw();},{passive:false});
 plot.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();inspect(selectedIndex+(event.key==='ArrowLeft'?-1:1));}else if(['+','=','-'].includes(event.key)){event.preventDefault();view.zoom(event.key==='-'?1.3:.75);range.value='custom';draw();}else if(event.key==='Home'||event.key==='End'){event.preventDefault();inspect(event.key==='Home'?view.first:view.last);}});
 back.addEventListener('click',()=>inspect(selectedIndex-1));next.addEventListener('click',()=>inspect(selectedIndex+1));slider.addEventListener('input',()=>inspect(Number(slider.value)));
 latest.addEventListener('click',()=>{const count=view.last-view.first+1;view.set(points.length-count,points.length-1);selectedIndex=points.length-1;draw();});
 reset.addEventListener('click',()=>{view.set(0,points.length-1);range.value='all';selectedIndex=points.length-1;draw();});
 range.addEventListener('change',()=>{if(range.value==='custom')return;const cutoff=range.value==='all'?-Infinity:Date.parse(points.at(-1).date)-(Number(range.value)-1)*86400000;view.set(points.findIndex(p=>Date.parse(p.date)>=cutoff),points.length-1);draw();});
 for(const control of [style,axis,averages,bands,volume])control?.addEventListener('change',draw);
 function fullscreenState(){expanded=document.fullscreenElement===section||section.getAttribute?.('data-expanded')==='true';full.textContent=expanded?'Exit fullscreen':'Fullscreen';full.setAttribute('aria-pressed',String(expanded));}
 full.addEventListener('click',()=>{expanded=!expanded;section.setAttribute('data-expanded',String(expanded));section.setAttribute('role',expanded?'dialog':'region');section.setAttribute('aria-modal',String(expanded));section.setAttribute('aria-label','Price history');fullscreenState();if(expanded)section.focus?.();else full.focus?.();});
 section.addEventListener('fullscreenchange',fullscreenState);section.addEventListener('keydown',event=>{if(event.key==='Escape'&&expanded){if(expanded){section.setAttribute('data-expanded','false');section.setAttribute('aria-modal','false');section.setAttribute('role','region');expanded=false;fullscreenState();full.focus?.();}}else if(event.key==='Tab'&&expanded){const focusable=[...section.querySelectorAll('button:not(:disabled),select,input,summary,[tabindex="0"]')].filter(n=>n.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(event.shiftKey&&(document.activeElement===first||document.activeElement===section)){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}});
 section.append(selected,navigation,plot,volumePlot,sliderLabel,help,status);
 const tools=el('details');tools.className='chart-tools';tools.append(el('summary','Advanced chart tools and exact values'),extraNavigation,controls,el('p',synthetic?'Demo candles use generated OHLC values. Overlays are illustrations computed from the same generated data; missing sessions are not filled.':'Blue: price · teal: MA7 · dashed orange: MA25 · dotted purple: bands. Candles show actual daily open/high/low/close; green closes at or above open and red below. Overlays use the original loaded history. Missing data is not filled.'),readout);
 const tableDetails=el('details'),table=el('table'),head=el('tr');
 table.append(el('caption',`${points.length} loaded observations · USD · oldest to newest. Zoom does not remove rows.`));
 const headers=[options.sessions?'Exchange session':'UTC date',hasBars?'Close (USD)':'Price (USD)','Change from previous observation (%)',...(hasBars?['Open (USD)','High (USD)','Low (USD)','Volume (shares)']:[]),'MA7 (USD)','MA25 (USD)','Lower band (USD)','Middle band (USD)','Upper band (USD)'];
 for(const text of headers){const th=el('th',text);th.setAttribute('scope','col');head.append(th);}table.append(head);
 let tableBuilt=false;
 tableDetails.addEventListener('toggle',()=>{if(!tableDetails.open||tableBuilt)return;tableBuilt=true;
 for(let index=0;index<points.length;index++){const p=points[index],row=el('tr'),b=hasBars?bars[index]:null;
  const change=index?((p.price/points[index-1].price-1)*100):null;
  const values=[p.date,p.price,change,...(b?[b.open,b.high,b.low,b.volume]:[]),p.ma_7,p.ma_25,p.bollinger_lower,p.bollinger_middle,p.bollinger_upper];
  values.forEach(value=>row.append(el('td',value===null||value===undefined?'Unavailable':format(value))));table.append(row);
 }
 });
 tableDetails.className='chart-table';tableDetails.append(el('summary','Chart data table'),el('p',`${hasBars?(synthetic?'OHLC and volume are generated demonstration values, not traded market prices.':'Open/high/low/close and share volume come from the loaded daily provider bars. Prices are split-adjusted; volume is not dollar turnover.'):'Prices are daily samples, not OHLC candles.'} Change compares consecutive available observations and may span a data gap. MA7 and MA25 average 7 and 25 observations. Bollinger Bands describe variation around the 20-observation average; they are not predicted prices. Unavailable means the value was not supplied or there is insufficient usable history. The first observation has no prior return. All rows retain the original analysis window.`),table);tools.append(tableDetails);section.append(candleDetails,candleGuide);
 if(options.sessions){const explanation=el('details');explanation.append(el('summary','About adjusted prices and scale'),el('p',synthetic?'All prices and volumes in this demo are generated formulas for fictional listings. No real split adjustments, market returns or prediction results are represented.':'Stock prices are requested on a split-adjusted basis, so older prices may differ from the prices originally quoted at the time. Reverse splits can make earlier values look very large. A split alone is not an investment gain or loss. Dividends are excluded. Adjustment accuracy depends on the provider; a large move is not independently verified by this chart.'),el('p','Linear scale compares dollar changes. Logarithmic scale compares percentage changes and is available only when every displayed value is positive. Missing sessions remain gaps.'));section.append(explanation);}
 section.append(tools);parent.append(section);draw();
}
