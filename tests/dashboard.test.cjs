// Run with node --test tests/dashboard.test.cjs (no dependencies or HTTP).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/assets/dashboard.js'), 'utf8');
class Element {
 constructor(tag='div') { this.tag=tag; this.children=[]; this.listeners={}; this.value=''; this.checked=false; this.disabled=false; this.text=''; }
 set textContent(v) { this.text=String(v); this.children=[]; }
 get textContent() { return this.text+this.children.map(x=>x.textContent).join(' '); }
 append(...nodes) { this.children.push(...nodes); }
 replaceChildren(...nodes) { this.text='';this.children=nodes; }
 addEventListener(type, fn) { this.listeners[type]=fn; }
 setAttribute(key, value) { this[key]=value; }
 reportValidity() { return true; }
}
function setup(storage = new Map()) {
 const elements=Object.fromEntries(['load-coins','catalog-status','coin-search','coin-options','coin-search-status','coin-quick','selected-coin','coin','days','include-position','amount','cost','status','analysis','ai','analysis-form','recommend'].map(id=>[id,new Element()]));
 elements.coin.value='bitcoin'; elements.days.value='90'; elements.amount.value='0'; elements.cost.value='0';
 const requests=[];
 for (const id of ['watchlist-add','watchlist-status','watchlist-items']) elements[id]=new Element();
 const context={Intl, document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),createDocumentFragment:()=>new Element('fragment')},fetch:(url, options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/visuals.js'), 'utf8'),context);
 vm.runInNewContext(source,context);
 context.localStorage={getItem:key=>storage.get(key) ?? null,setItem:(key,value)=>storage.set(key,value)};
 const windowEvents={}; context.window={addEventListener:(name,fn)=>{windowEvents[name]=fn;}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/watchlist.js'), 'utf8'),context);
 const click=()=>elements.recommend.listeners.click();
 const analyze=()=>elements['analysis-form'].listeners.submit({preventDefault(){}});
 const answer=(index, body, status=200)=>requests[index].resolve({ok:status===200,status,json:async()=>body});
 return {elements,requests,click,analyze,answer,storage,windowEvents};
}

test('watchlist persists across reloads, prevents duplicates and removes explicitly',()=>{
 const s=setup(); const add=()=>s.elements['watchlist-add'].listeners.click();
 add(); add(); assert.match(s.elements['watchlist-status'].textContent,/already/);
 const next=setup(s.storage);
 assert.match(next.elements['watchlist-items'].textContent,/Bitcoin/);
 next.elements['watchlist-items'].children[0].children[1].listeners.click();
 assert.match(setup(s.storage).elements['watchlist-items'].textContent,/empty/);
 assert.equal(s.requests.length,0); assert.equal(next.requests.length,0);
});

test('watchlist custom selection discards stale AI and keeps pending lock',async()=>{
 const s=setup(); s.elements.coin.value='custom-token'; s.elements['watchlist-add'].listeners.click();
 s.elements.coin.value='bitcoin'; const pending=s.click();
 s.elements['watchlist-items'].children[0].children[0].listeners.click();
 assert.equal(s.elements.coin.value,'custom-token'); assert.equal(s.elements.recommend.disabled,true);
 s.answer(0,completed()); await pending;
 assert.doesNotMatch(s.elements.ai.textContent,/HOLD/); assert.equal(s.requests.length,1);
});

test('invalid watchlist is preserved and storage failure does not claim success',()=>{
 const storage=new Map([['crypto-analyzer.watchlist.v1','broken json']]); const s=setup(storage);
 s.elements['watchlist-add'].listeners.click(); assert.equal(storage.get('crypto-analyzer.watchlist.v1'),'broken json');
 assert.match(s.elements['watchlist-status'].textContent,/not saved/);
 const broken={get:()=>null,set:()=>{throw new Error('quota');}}; const t=setup(broken);
 t.elements['watchlist-add'].listeners.click(); assert.match(t.elements['watchlist-status'].textContent,/not saved/);
 assert.match(t.elements['watchlist-items'].textContent,/empty/);
});

test('watchlist rereads before mutations and refreshes on another tab update',()=>{
 const a=setup(), b=setup(a.storage); a.elements['watchlist-add'].listeners.click();
 b.elements.coin.value='ethereum'; b.elements['watchlist-add'].listeners.click();
 a.windowEvents.storage({key:'crypto-analyzer.watchlist.v1'});
 assert.match(a.elements['watchlist-items'].textContent,/Bitcoin/); assert.match(a.elements['watchlist-items'].textContent,/Ethereum/);
});
function evidence(price=189) { return {coin_id:'bitcoin',generated_at_utc:'2026-09-19',window:{expected_start:'start',expected_end:'end',start:'start',end:'end',observations:90,missing_days:0,leading_missing_days:0,internal_missing_days:0,trailing_missing_days:0,latest_observation_age_days:0},indicators:{latest_history_price_usd:price,live_price_usd:null},backtest:{closed_trades:0,asset_max_drawdown_pct:0,win_rate_pct:null},portfolio:{included:false},limitations:['sample limitation']}; }
function completed() {return {evidence:evidence(777),model:'fake',recommendation_status:'completed',recommendation:{action:'HOLD',confidence:'low',confidence_explanation:'test',summary:'<img onerror=alert(1)>',reasons:[{explanation:'price',evidence_keys:['indicators.latest_history_price_usd']}],risks:[]}};}
test('no automatic requests; preserve zero and null',async()=>{const s=setup();assert.equal(s.requests.length,0);const p=s.analyze();s.answer(0,evidence());await p;assert.match(s.elements.analysis.textContent,/Live price \(USD\) N\/A/);assert.match(s.elements.analysis.textContent,/Closed trades 0/);});
test('AI cites its own snapshot and renders hostile strings literally',async()=>{const s=setup();let p=s.analyze();s.answer(0,evidence());await p;p=s.click();s.answer(1,completed());await p;assert.match(s.elements.ai.textContent,/indicators.latest_history_price_usd 777/);assert.match(s.elements.ai.textContent,/<img onerror=alert\(1\)>/);assert.doesNotMatch(s.elements.analysis.textContent,/777/);});
test('global pending lock survives selection changes and ignores stale AI',async()=>{const s=setup();const p=s.click();await s.click();assert.equal(s.requests.length,1);s.elements.coin.value='ethereum';s.elements.coin.listeners.input();assert.equal(s.elements.recommend.disabled,true);await s.click();assert.equal(s.requests.length,1);s.answer(0,completed());await p;assert.doesNotMatch(s.elements.ai.textContent,/HOLD/);assert.equal(s.elements.recommend.disabled,false);});
test('latest analysis wins when responses arrive out of order',async()=>{const s=setup();const a=s.analyze(),b=s.analyze();s.answer(1,evidence(222));await b;s.answer(0,evidence(111));await a;assert.match(s.elements.analysis.textContent,/222/);assert.doesNotMatch(s.elements.analysis.textContent,/111/);});
test('AI unavailable retains evidence',async()=>{const s=setup();const p=s.click();s.answer(0,{recommendation_status:'unavailable',evidence:evidence(),recommendation:null});await p;assert.match(s.elements.ai.textContent,/Raw evidence/);assert.match(s.elements.ai.textContent,/189/);});
test('coverage errors are visible without echoing raw error body',async()=>{const s=setup();const p=s.analyze();s.answer(0,{error:{message:'SECRET'},coverage:evidence().window},503);await p;assert.match(s.elements.analysis.textContent,/insufficient or stale/);assert.match(s.elements.analysis.textContent,/Requested UTC dates/);assert.doesNotMatch(s.elements.analysis.textContent,/SECRET/);});
test('malformed recommendation does not leave a partial decision',async()=>{const s=setup();const p=s.click();const r=completed();r.recommendation.reasons[0].evidence_keys=['invented'];s.answer(0,r);await p;assert.doesNotMatch(s.elements.ai.textContent,/HOLD/);assert.match(s.elements.status.textContent,/failed/);assert.equal(s.requests.length,1);});
test('position omitted by default and sent only when enabled',async()=>{const s=setup();let p=s.click();assert.equal(JSON.parse(s.requests[0].options.body).selected_position,undefined);s.answer(0,{recommendation_status:'unavailable',evidence:evidence()});await p;s.elements['include-position'].checked=true;s.elements.amount.value='2';s.elements.cost.value='100';p=s.click();assert.deepEqual(JSON.parse(s.requests[1].options.body).selected_position,{amount:2,avg_buy_price:100});s.answer(1,{recommendation_status:'unavailable',evidence:evidence()});await p;});

test('malformed evidence is rejected instead of displayed as missing data',async()=>{const s=setup();const p=s.analyze();s.answer(0,{coin_id:'bitcoin',generated_at_utc:'now',window:{},indicators:{},backtest:{},portfolio:{},limitations:[]});await p;assert.match(s.elements.status.textContent,/unavailable/);assert.doesNotMatch(s.elements.analysis.textContent,/Historical price/);});

test('safe AI error is rendered literally while evidence remains available',async()=>{const s=setup();const p=s.click();s.answer(0,{recommendation_status:'unavailable',evidence:evidence(),recommendation:null,ai_error:{code:'ai_unavailable',message:'Provider unavailable <img onerror=alert(1)>'}});await p;assert.match(s.elements.ai.textContent,/Provider unavailable <img onerror=alert\(1\)>/);assert.match(s.elements.ai.textContent,/189/);});
for (const message of ['Failed to fetch','NetworkError when attempting to fetch resource.','Load failed']) {
 test('connection failure normalized: '+message,async()=>{const s=setup();const p=s.click();s.requests[0].reject(new TypeError(message));await p;assert.match(s.elements.ai.textContent,/Could not connect to the local server/);assert.equal(s.elements.recommend.disabled,false);assert.equal(s.requests.length,1);});
}

function descendants(n) { return [n,...n.children.flatMap(descendants)]; }
function chartPoints() { return ['2026-09-01','2026-09-02','2026-09-04'].map((date,i)=>({date,price:100,ma_7:i?100:null,ma_25:null,bollinger_lower:null,bollinger_middle:null,bollinger_upper:null})); }
test('chart preserves gaps, handles flat values, and offers keyboard inspection',async()=>{const s=setup();const p=s.analyze();s.answer(0,{...evidence(100),history:chartPoints()});await p;const nodes=descendants(s.elements.analysis);const paths=nodes.filter(n=>n.tag==='path');assert.equal((paths[0].d.match(/M/g)||[]).length,2);assert.doesNotMatch(paths[0].d,/NaN|Infinity/);const slider=nodes.find(n=>n.type==='range');slider.value='0';slider.listeners.input();assert.match(s.elements.analysis.textContent,/2026-09-01 UTC/);assert.match(s.elements.analysis.textContent,/Chart data table/);const bands=nodes.filter(n=>n.type==='checkbox')[1];bands.checked=true;bands.listeners.change();assert.equal(descendants(s.elements.analysis).filter(n=>n.tag==='path').length,6);});
test('plain language is descriptive and warns about no completed trades',async()=>{const s=setup();const p=s.analyze();s.answer(0,{...evidence(),indicators:{latest_history_price_usd:189,ma_25:180,rsi_14:70,macd_histogram:-1}});await p;assert.match(s.elements.analysis.textContent,/above its 25-observation average/);assert.match(s.elements.analysis.textContent,/does not predict a reversal/);assert.match(s.elements.analysis.textContent,/cannot estimate a win rate/);assert.match(s.elements.analysis.textContent,/Technical details and limitations/);});

test('coin search filters by symbol without changing selection or fetching',()=>{const s=setup();s.elements['coin-search'].value=' eth ';s.elements['coin-search'].listeners.input();assert.equal(s.elements['coin-options'].children.length,2);assert.equal(s.elements['coin-options'].children[0].value,'');assert.equal(s.elements['coin-options'].children[1].value,'ethereum');assert.equal(s.elements.coin.value,'bitcoin');assert.equal(s.requests.length,0);});
test('picker selects canonical ID, invalidates results and labels response',async()=>{const s=setup();s.elements['coin-options'].value='ripple';s.elements['coin-options'].listeners.change();assert.equal(s.elements.coin.value,'ripple');assert.match(s.elements['selected-coin'].textContent,/XRP/);const p=s.analyze();assert.match(s.requests[0].url,/analysis\/ripple/);s.answer(0,{...evidence(),coin_id:'ripple'});await p;assert.match(s.elements.analysis.textContent,/XRP \(XRP\) · ripple/);});
test('empty search keeps existing selection and supports custom IDs',()=>{const s=setup();s.elements['coin-search'].value='unknown';s.elements['coin-search'].listeners.input();assert.equal(s.elements['coin-options'].disabled,true);assert.match(s.elements['coin-search-status'].textContent,/No coins match/);assert.equal(s.elements.coin.value,'bitcoin');s.elements.coin.value='custom-token';s.elements.coin.listeners.input();assert.match(s.elements['selected-coin'].textContent,/custom-token/);});
test('quick choice preserves AI pending lock and discards old result',async()=>{const s=setup();const p=s.click();s.elements['coin-quick'].children[1].listeners.click();assert.equal(s.elements.coin.value,'ethereum');assert.equal(s.elements.recommend.disabled,true);s.answer(0,completed());await p;assert.doesNotMatch(s.elements.ai.textContent,/HOLD/);assert.equal(s.requests.length,1);});

test('full catalog loads once per click; filtering and selecting use canonical IDs',async()=>{const s=setup();const p=s.elements['load-coins'].listeners.click();await s.elements['load-coins'].listeners.click();assert.equal(s.requests.length,1);s.answer(0,{coins:[{id:'other-token',name:'Other Token',symbol:'OT'}],stale:false,fetched_at_utc:'now'});await p;s.elements['coin-search'].value='ot';s.elements['coin-search'].listeners.input();assert.equal(s.elements['coin-options'].children[1].value,'other-token');s.elements['coin-options'].value='other-token';s.elements['coin-options'].listeners.change();assert.equal(s.elements.coin.value,'other-token');assert.equal(s.requests.length,1);});

test('manual coin editing keeps the dropdown consistent',()=>{
 const s=setup(); s.elements.coin.value='ethereum'; s.elements.coin.listeners.input();
 assert.equal(s.elements['coin-options'].value,'ethereum');
 s.elements.coin.value='custom-token'; s.elements.coin.listeners.input();
 assert.equal(s.elements['coin-options'].value,'');
 assert.match(s.elements['selected-coin'].textContent,/custom-token/);
 assert.equal(s.requests.length,0);
});

for (const [price,position] of [[90,'below'],[100,'within'],[110,'within'],[120,'above']]) {
 test('Bollinger explanation for price '+price,async()=>{
  const s=setup(), p=s.analyze();
  s.answer(0,{...evidence(price),indicators:{latest_history_price_usd:price,bollinger_lower:100,bollinger_upper:110,support:[130],resistance:[80]}});
  await p;
  assert.match(s.elements.analysis.textContent,new RegExp('Price is '+position+' the bands'));
  assert.match(s.elements.analysis.textContent,/not a forecast range/);
  assert.match(s.elements.analysis.textContent,/not necessarily below/);
 });
}
test('catalog failure retains fallback and permits retry',async()=>{const s=setup();const p=s.elements['load-coins'].listeners.click();s.requests[0].reject(new Error('offline'));await p;assert.match(s.elements['catalog-status'].textContent,/manual ID entry still work/);assert.equal(s.elements['load-coins'].disabled,false);assert.equal(s.elements.coin.value,'bitcoin');});
