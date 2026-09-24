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
 reportValidity() { return true; }
}
function setup() {
 const elements=Object.fromEntries(['coin','days','include-position','amount','cost','status','analysis','ai','analysis-form','recommend'].map(id=>[id,new Element()]));
 elements.coin.value='bitcoin'; elements.days.value='90'; elements.amount.value='0'; elements.cost.value='0';
 const requests=[];
 const context={Intl, document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('fragment')},fetch:(url, options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
 vm.runInNewContext(source,context);
 const click=()=>elements.recommend.listeners.click();
 const analyze=()=>elements['analysis-form'].listeners.submit({preventDefault(){}});
 const answer=(index, body, status=200)=>requests[index].resolve({ok:status===200,status,json:async()=>body});
 return {elements,requests,click,analyze,answer};
}
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
