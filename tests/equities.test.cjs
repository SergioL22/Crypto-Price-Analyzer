const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const key='research-desk.equities.v1',id='twelvedata:stock:XNYS:USD:ABC';
class E {
 constructor(){this.children=[];this.listeners={};this.value='';this.disabled=false;this.text='';this.files=[];}
 append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.text='';this.children=nodes;}
 get textContent(){return this.text+this.children.map(x=>x.textContent).join(' ');}set textContent(v){this.text=String(v);this.children=[];}
 get options(){return this.children;}addEventListener(name,fn){this.listeners[name]=fn;}
}
function setup(file='equities.js',initial={version:1,listings:[{id,name:'Example'}],holdings:[],alerts:[]}){
 const names=['equity-list','equity-status','equity-save','equity-save-status','stock-options','equity-holding','equity-holding-form','equity-quantity','equity-cost','equity-remove-holding','equity-value','equity-valuation','equity-holdings','equity-alert-listing','equity-alert-type','equity-alert-direction','equity-alert-threshold','equity-alert-form','equity-alerts','equity-check','equity-check-result','equity-restore-file','equity-restore-preview','equity-restore-apply','equity-monitor-start','equity-monitor-stop','equity-monitor-status','equity-monitor-results','screen-list','screen-status','screen-results','screen-order','screen-add','screen-run'];
 const elements=Object.fromEntries(names.map(n=>[n,new E()])),storage=new Map([[key,JSON.stringify(initial)]]),requests=[];
 const timers=[],events={},windowEvents={};let now=Date.now();const Clock=class extends Date{constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}};
 const context={setTimeout:(fn,delay)=>{const timer={fn,delay};timers.push(timer);return timer;},clearTimeout:timer=>{timer.cancelled=true;},Intl,Date:Clock,Set,Map,JSON,Number,Array,window:{addEventListener:(name,fn)=>windowEvents[name]=fn,confirm:()=>true},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},document:{addEventListener:(name,fn)=>events[name]=fn,getElementById:n=>elements[n],createElement:()=>new E()},fetch:(url)=>new Promise(resolve=>requests.push({url,resolve}))};
 for(const name of ['common.js',file])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/assets',name),'utf8'),context);
 const picker=elements['stock-options'];picker.value=id;const option=new E();option.value=id;option.textContent='Example';picker.append(option);
 return {timers,events,windowEvents,context,advance:ms=>now+=ms,e:elements,storage,requests,answer:(i,data)=>requests[i].resolve({ok:true,json:async()=>data}),data:()=>JSON.parse(storage.get(key))};
}
test('equity watchlist is qualified, duplicate safe and makes no automatic requests',()=>{
 const s=setup();s.e['equity-save'].listeners.click();assert.equal(s.data().listings.length,1);assert.equal(s.requests.length,0);
 assert.equal(s.e['equity-list'].children[0].children[0].href,'/stocks.html?asset='+encodeURIComponent(id));
 s.e['stock-options'].value='javascript:bad';s.e['equity-save'].listeners.click();assert.equal(s.data().listings.length,1);
});
test('equity holdings validate and save separately from crypto storage',()=>{
 const s=setup();s.storage.set('crypto-analyzer.watchlist.v1','unchanged');s.e['equity-holding'].value=id;s.e['equity-quantity'].value='2';s.e['equity-cost'].value='15';s.e['equity-holding-form'].listeners.submit({preventDefault(){}});
 assert.equal(s.data().holdings[0].quantity,2);assert.equal(s.storage.get('crypto-analyzer.watchlist.v1'),'unchanged');
 s.e['equity-quantity'].value='Infinity';s.e['equity-holding-form'].listeners.submit({preventDefault(){}});assert.equal(s.data().holdings[0].quantity,2);
});
test('equity valuation ignores a holding edited during the request',async()=>{
 const s=setup('equities.js',{version:1,listings:[{id,name:'Example'}],holdings:[{id,quantity:2,cost:10}],alerts:[]});s.e['equity-holding'].value=id;
 const pending=s.e['equity-value'].listeners.click();const data=s.data();data.holdings[0].quantity=3;s.storage.set(key,JSON.stringify(data));s.answer(0,{history:[{date:'2026-10-06',price:20}],window:{latest_closed_session:'2026-10-06'}});await pending;assert.match(s.e['equity-valuation'].textContent,/Holding changed/);
});
test('equity alerts retain state when the latest close is missing and suppress repeated matches',async()=>{
 const s=setup('equities.js',{version:1,listings:[{id,name:'Example'}],holdings:[],alerts:[{id,type:'price',direction:'above',threshold:10,triggered:false}]});s.e['equity-alert-listing'].value=id;
 let pending=s.e['equity-check'].listeners.click();s.answer(0,{history:[{date:'2026-10-05',price:20}],window:{latest_closed_session:'2026-10-06'}});await pending;assert.equal(s.data().alerts[0].triggered,false);
 for(let i=1;i<=2;i++){pending=s.e['equity-check'].listeners.click();s.answer(i,{history:[{date:'2026-10-06',price:20}],window:{latest_closed_session:'2026-10-06'}});await pending;}
 assert.equal(s.data().alerts[0].triggered,true);assert.match(s.e['equity-check-result'].textContent,/still matches/);
});
test('equity restore detects stale preview and preserves existing data',async()=>{
 const s=setup();s.e['equity-restore-file'].files=[{size:50,text:async()=>JSON.stringify({version:1,listings:[],holdings:[],alerts:[]})}];await s.e['equity-restore-preview'].listeners.click();const updated=s.data();updated.listings[0].name='Changed';s.storage.set(key,JSON.stringify(updated));s.e['equity-restore-apply'].listeners.click();assert.equal(s.data().listings[0].name,'Changed');assert.match(s.e['equity-status'].textContent,/Workspace changed/);
});
test('invalid equity storage is not overwritten',()=>{
 const s=setup('equities.js',{version:500});const before=s.storage.get(key);s.e['equity-save'].listeners.click();assert.equal(s.storage.get(key),before);
});
test('free comparison uses prior-year close and labels selected-universe results',async()=>{
 const s=setup('screener.js');s.e['screen-order'].value='ytd_return';s.e['screen-add'].listeners.click();assert.equal(s.requests.length,0);
 const year=new Date().getFullYear();const pending=s.e['screen-run'].listeners.click();s.answer(0,{bars:[{date:`${year-1}-12-31`,close:100,volume:100},{date:`${year}-01-02`,close:110,volume:200}],window:{complete:true,latest_closed_session:`${year}-01-02`}});await pending;
 assert.match(s.e['screen-results'].textContent,/10.00%/);assert.match(s.e['screen-status'].textContent,/not a whole-market/);
});
test('free comparison excludes incomplete windows instead of fabricating a ranking',async()=>{
 const s=setup('screener.js');s.e['screen-order'].value='ytd_return';s.e['screen-add'].listeners.click();const pending=s.e['screen-run'].listeners.click();s.answer(0,{bars:[],window:{complete:false}});await pending;assert.match(s.e['screen-results'].textContent,/unavailable/);assert.match(s.e['screen-status'].textContent,/stopped/);
});

const monitorWorkspace=()=>({version:1,listings:[{id,name:'Example'}],holdings:[],alerts:[{id,type:'price',direction:'above',threshold:10,triggered:false}]});
const closeData=(price=20,date='2026-10-16')=>({history:[{date,price}],window:{latest_closed_session:'2026-10-16'},history_source:{fetched_at_utc:'2026-10-16T21:00:00Z'}});
test('monitor is opt-in, records evidence and suppresses repeat matches',async()=>{const s=setup('equities.js',monitorWorkspace());assert.equal(s.requests.length,0);let p=s.e['equity-monitor-start'].listeners.click();s.answer(0,closeData());await p;assert.equal(s.data().alerts[0].triggered,true);assert.match(s.e['equity-monitor-results'].textContent,/NEW MATCH/);assert.match(s.e['equity-monitor-results'].textContent,/Checked/);assert.match(s.e['equity-monitor-results'].textContent,/2026-10-16/);assert.equal(s.timers.at(-1).delay,60000);s.advance(60000);p=s.timers.at(-1).fn();s.answer(1,closeData());await p;assert.match(s.e['equity-monitor-results'].textContent,/Still matches/);s.advance(60000);p=s.timers.at(-1).fn();s.answer(2,closeData(10));await p;assert.equal(s.data().alerts[0].triggered,false);s.e['equity-monitor-stop'].listeners.click();assert.equal(s.timers.at(-1).cancelled,true);});
test('monitor rejects stale outcomes and stops without changing saved rules',async()=>{const s=setup('equities.js',monitorWorkspace());const p=s.e['equity-monitor-start'].listeners.click();s.answer(0,closeData(20,'2026-10-15'));await p;assert.equal(s.data().alerts[0].triggered,false);assert.match(s.e['equity-monitor-status'].textContent,/Monitoring stopped/);assert.equal(s.timers.length,0);});
test('monitor stops on provider failure without retrying',async()=>{const s=setup();const p=s.e['equity-monitor-start'].listeners.click();s.requests[0].resolve({ok:false,status:503,json:async()=>({error:{code:'stock_quota'}})});await p;assert.match(s.e['equity-monitor-status'].textContent,/quota/);assert.equal(s.timers.length,0);assert.equal(s.e['equity-monitor-start'].disabled,false);});
test('hidden pages discard pending observations and cancel monitoring',async()=>{const s=setup('equities.js',monitorWorkspace());const p=s.e['equity-monitor-start'].listeners.click();s.context.document.hidden=true;s.events.visibilitychange();s.answer(0,closeData());await p;assert.equal(s.data().alerts[0].triggered,false);assert.doesNotMatch(s.e['equity-monitor-results'].textContent,/NEW MATCH/);assert.equal(s.timers.length,0);});
test('monitor waits for shared cooldown and uses the current watchlist',async()=>{const s=setup();s.storage.set('research-desk.monitor-attempt.v1',String(s.context.Date.now()));await s.e['equity-monitor-start'].listeners.click();assert.equal(s.requests.length,0);assert.ok(s.timers[0].delay>0);assert.equal(s.timers.length,1);});
test('monitor discards checks when rules were edited during a request',async()=>{const s=setup('equities.js',monitorWorkspace());const p=s.e['equity-monitor-start'].listeners.click();const data=s.data();data.alerts[0].threshold=999;s.storage.set(key,JSON.stringify(data));s.answer(0,closeData());await p;assert.equal(s.data().alerts[0].threshold,999);assert.equal(s.data().alerts[0].triggered,false);assert.match(s.e['equity-monitor-status'].textContent,/changed/);});

test('monitor rotates through listings serially and retains unavailable RSI state',async()=>{const workspace=monitorWorkspace(),second=id.replace(':ABC',':XYZ');workspace.listings.push({id:second,name:'Second'});workspace.alerts.push({id:second,type:'rsi',direction:'below',threshold:30,triggered:true});const s=setup('equities.js',workspace);let p=s.e['equity-monitor-start'].listeners.click();s.answer(0,closeData());await p;s.advance(60000);p=s.timers.at(-1).fn();assert.match(s.requests[1].url,/XYZ/);s.answer(1,closeData());await p;assert.equal(s.data().alerts[1].triggered,true);assert.match(s.e['equity-monitor-results'].textContent,/unavailable; saved state retained/);});


test('new saves record a UTC date without resetting existing watchlist dates',()=>{
 const s=setup('equities.js',{version:1,listings:[],holdings:[],alerts:[]});s.e['equity-save'].listeners.click();
 const date=s.data().listings[0].saved_on;assert.equal(date,new Date(s.context.Date.now()).toISOString().slice(0,10));
 s.advance(86400000);s.e['equity-save'].listeners.click();assert.equal(s.data().listings[0].saved_on,date);
});
test('watchlist metadata survives unrelated edits and invalid saved dates preserve storage',()=>{
 const initial={version:1,listings:[{id,name:'Example',saved_on:'2026-10-01'}],holdings:[],alerts:[]};const s=setup('equities.js',initial);
 s.e['equity-holding'].value=id;s.e['equity-quantity'].value='1';s.e['equity-cost'].value='20';s.e['equity-holding-form'].listeners.submit({preventDefault(){}});
 assert.equal(s.data().listings[0].saved_on,'2026-10-01');
 const invalid={...initial,listings:[{id,name:'Bad',saved_on:'2026-02-30'}]};const bad=setup('equities.js',invalid),before=bad.storage.get(key);bad.e['equity-save'].listeners.click();assert.equal(bad.storage.get(key),before);
});
test('comparison offers ascending YTD performance only within the chosen list',async()=>{
 const s=setup('screener.js');s.e['screen-order'].value='worst_ytd';s.e['screen-add'].listeners.click();
 const second=new E();second.value=id.replace('ABC','XYZ');second.textContent='Second';s.e['stock-options'].append(second);s.e['stock-options'].value=second.value;s.e['screen-add'].listeners.click();
 const year=new Date().getFullYear(),data=close=>({bars:[{date:`${year-1}-12-31`,close:100,volume:100},{date:`${year}-01-02`,close,volume:100}],window:{complete:true,latest_closed_session:`${year}-01-02`}});
 const pending=s.e['screen-run'].listeners.click();s.answer(0,data(110));await new Promise(r=>setImmediate(r));s.answer(1,data(90));await pending;
 assert.match(s.e['screen-results'].children[0].textContent,/Second/);assert.match(s.e['screen-status'].textContent,/not a whole-market/);
});
