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
function setup(storage = new Map(),debounce=false,route=null) {
 const elements=Object.fromEntries(['load-coins','catalog-status','coin-search','coin-options','coin-search-status','coin-quick','selected-coin','coin','days','include-position','amount','cost','status','analysis','ai','analysis-form','recommend'].map(id=>[id,new Element()]));
 elements.coin.value='bitcoin'; elements.days.value='90'; elements.amount.value='0'; elements.cost.value='0';
 const requests=[],documentEvents={};
 for (const id of ['stock-kind','stock-search','stock-options','stock-status','stock-results','stock-load','stock-run','stock-days','stock-matches','stock-more','stock-form','stock-exchange','stock-query-mode','stock-sort','stock-reset-filters','stock-refresh','stock-initial','stock-listing-summary','stock-period','stock-retry']) elements[id]=new Element();
 elements['stock-kind'].value='stock'; elements['stock-days'].value='90';
 for (const id of ['restore-file','restore-preview','restore-apply','restore-agree','restore-status','restore-details','alert-form','alerts-load','alerts-check','alerts-status','alerts-list','alerts-history','alert-save','alert-coin','alert-type','alert-direction','alert-threshold']) elements[id]=new Element();
 elements['alert-type'].value='price'; elements['alert-direction'].value='above';
 const downloads=[], objectUrls=[], revokedUrls=[], timers=[];
 for (const id of ['holdings-export','backup-status']) elements[id]=new Element();
 for (const id of ['holdings-load','holdings-form','holding-save','holdings-status','holdings-existing','holding-coin','holding-amount','holding-cost']) elements[id]=new Element();
 for (const id of ['watchlist-add','watchlist-status','watchlist-items','portfolio-load','portfolio-status','portfolio-results']) elements[id]=new Element();
 const context={Intl, document:{addEventListener:(name,fn)=>documentEvents[name]=fn,getElementById:id=>elements[id],createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),createDocumentFragment:()=>new Element('fragment')},fetch:(url, options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
 context.Blob=Blob;
 context.URL={createObjectURL:blob=>{objectUrls.push(blob);return 'blob:sample';},revokeObjectURL:url=>revokedUrls.push(url)};
 context.setTimeout=fn=>timers.push(fn);
 if(debounce)context.clearTimeout=id=>{if(timers[id-1])timers[id-1].cancelled=true;};
 context.document.body={append:link=>{link.click=()=>downloads.push({href:link.href,name:link.download});link.remove=()=>{};}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/common.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/visuals.js'), 'utf8'),context);
 vm.runInNewContext(source,context);
 context.localStorage={getItem:key=>storage.get(key) ?? null,setItem:(key,value)=>storage.set(key,value)};
 if(route){context.URLSearchParams=URLSearchParams;context.document.body.dataset={demo:route.demo?'true':'false'};}
 const windowEvents={}; context.window={location:route?{search:route.search}:undefined,addEventListener:(name,fn)=>{windowEvents[name]=fn;}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/watchlist.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/portfolio.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/holdings.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/backup.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/restore.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/alerts.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/listing-discovery.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/company-profile.js'), 'utf8'),context);
 vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/assets/stocks.js'), 'utf8'),context);
 const click=()=>elements.recommend.listeners.click();
 const analyze=()=>elements['analysis-form'].listeners.submit({preventDefault(){}});
 const answer=(index, body, status=200)=>requests[index].resolve({ok:status===200,status,json:async()=>body});
 return {setView:view=>context.document.body.dataset={view},documentEvents,elements,requests,click,analyze,answer,storage,windowEvents,downloads,objectUrls,revokedUrls,timers};
}

test('explicit stock catalog reload discards an obsolete asset type',async()=>{
 const s=setup(); assert.equal(s.requests.length,0);
 const pending=s.elements['stock-load'].listeners.click();
 assert.equal(s.requests[0].url,'/v1/assets?asset_class=stock');
 s.elements['stock-kind'].value='etf'; s.elements['stock-kind'].listeners.change();
 s.answer(0,{assets:[{id:'old',symbol:'OLD',name:'Old',exchange:'XNYS',currency:'USD'}],stale:false}); await pending;
 assert.equal(s.elements['stock-options'].children.length,1);
 assert.equal(s.elements['stock-options'].value,'');
 assert.equal(s.elements['stock-run'].disabled,true);
});

test('stock research ignores a response after changing the selected listing',async()=>{
 const s=setup(); s.elements['stock-options'].value='twelvedata:stock:XNYS:USD:ABC';
 const pending=s.elements['stock-form'].listeners.submit({preventDefault(){}});
 assert.match(s.requests[0].url,/asset_id=twelvedata%3Astock%3AXNYS%3AUSD%3AABC/);
 s.elements['stock-options'].listeners.change();
 s.answer(0,{}); await pending;
 assert.equal(s.elements['stock-results'].textContent,'');
});

test('stock loading state recovers after errors without repeating a request',async()=>{
 const s=setup();const catalog=s.elements['stock-load'].listeners.click();
 assert.equal(s.elements['stock-load']['aria-busy'],'true');
 s.answer(0,{},503);await catalog;
 assert.equal(s.elements['stock-load']['aria-busy'],'false');
 assert.equal(s.elements['stock-load'].disabled,false);
 s.elements['stock-options'].value='twelvedata:stock:XNYS:USD:ABC';
 const pending=s.elements['stock-form'].listeners.submit({preventDefault(){}});
 assert.equal(s.elements['stock-results']['aria-busy'],'true');
 assert.equal(s.elements['stock-run'].textContent,'Loading analysis…');
 s.answer(1,{},503);await pending;
 assert.equal(s.elements['stock-results']['aria-busy'],'false');
 assert.equal(s.elements['stock-run'].textContent,'Update analysis');
 assert.equal(s.requests.length,2);
});

test('stock dropdown pages the full catalog, sorts, and searches all names without requests',async()=>{
 const s=setup(); const pending=s.elements['stock-load'].listeners.click();
 const assets=Array.from({length:350},(_,i)=>({id:`asset-${i}`,name:`Company ${String(i).padStart(3,'0')}`,symbol:`T${i}`,exchange:'XNYS',currency:'USD'})).reverse();
 s.answer(0,{assets,stale:false}); await pending;
 const picker=s.elements['stock-options'];
 assert.equal(picker.children.length,201);assert.equal(s.elements['stock-more'].hidden,false);s.elements['stock-more'].listeners.click();assert.equal(picker.children.length,351);assert.equal(s.elements['stock-more'].hidden,true);
 assert.match(picker.children[1].textContent,/^Company 000 \(T0\)/);
 assert.match(picker.children.at(-1).textContent,/Company 349/);
 assert.equal(s.elements['stock-run'].disabled,true);
 picker.value='asset-349'; const analysis=picker.listeners.change(); assert.equal(s.elements['stock-run'].disabled,true);assert.equal(s.requests.length,2);s.answer(1,{error:{message:'unavailable'}},503);await analysis;
 s.elements['stock-search'].value='Company 349'; s.elements['stock-search'].listeners.input();
 assert.equal(picker.children.length,2); assert.equal(picker.value,'asset-349');
 s.elements['stock-search'].value='no such company'; s.elements['stock-search'].listeners.input();
 assert.equal(picker.value,''); assert.equal(s.elements['stock-run'].disabled,true);
 assert.equal(s.requests.length,2);
});

test('stock scripts initialize independently without crypto elements or requests',()=>{
 const ids=['stock-kind','stock-search','stock-options','stock-status','stock-results','stock-load','stock-run','stock-days','stock-matches','stock-form'];
 const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));
 const context={Intl,document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},fetch:()=>assert.fail('Unexpected request')};
 for(const file of ['common.js','visuals.js','listing-discovery.js','company-profile.js','stocks.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/assets',file),'utf8'),context);
 assert.equal(elements['stock-run'].disabled,true);
 assert.match(elements['stock-options'].children[0].textContent,/Load the list/);
});

test('stock discovery sorts by ticker and exact searches never request more data',async()=>{
 const s=setup(),pending=s.elements['stock-load'].listeners.click();
 s.answer(0,{assets:[{id:'one',name:'Alpha',symbol:'ZZZ',exchange:'XNYS',currency:'USD'},{id:'two',name:'Bravo',symbol:'AAA',exchange:'XNGS',currency:'USD'}],stale:false});await pending;
 s.elements['stock-sort'].value='symbol';s.elements['stock-sort'].listeners.change();assert.match(s.elements['stock-options'].children[1].textContent,/Bravo/);
 s.elements['stock-query-mode'].value='ticker';s.elements['stock-query-mode'].listeners.change();s.elements['stock-search'].value='aaa';s.elements['stock-search'].listeners.input();assert.equal(s.elements['stock-options'].children.length,2);
 s.elements['stock-search'].value='aa';s.elements['stock-search'].listeners.input();assert.equal(s.elements['stock-options'].children.length,1);assert.equal(s.requests.length,1);
 s.elements['stock-reset-filters'].listeners.click();assert.equal(s.elements['stock-options'].children.length,3);assert.equal(s.requests.length,1);
});

test('fresh-history checkbox changes only an explicit analysis request',async()=>{
 const s=setup();s.elements['stock-results'].textContent='Previous analysis';s.elements['stock-options'].value='selected';s.elements['stock-refresh'].checked=true;s.elements['stock-refresh'].listeners.change?.();assert.equal(s.requests.length,0);assert.equal(s.elements['stock-results'].textContent,'Previous analysis');
 const pending=s.elements['stock-form'].listeners.submit({preventDefault(){}});assert.match(s.requests[0].url,/refresh=true/);s.answer(0,{},503);await pending;assert.equal(s.requests.length,1);
});

test('stock setup errors give setup instructions without provider text',async()=>{
 const s=setup(); const pending=s.elements['stock-load'].listeners.click();
 s.answer(0,{error:{code:'stock_setup_required',message:'secret text'}},503); await pending;
 assert.match(s.elements['stock-status'].textContent,/TWELVE_DATA_API_KEY/);
 assert.doesNotMatch(s.elements['stock-status'].textContent,/secret/);
 assert.equal(s.elements['stock-load'].disabled,false);
});

test('stock chart connects weekends but breaks missing trading sessions',async()=>{
 const s=setup(); s.elements['stock-options'].value='sample';
 const pending=s.elements['stock-form'].listeners.submit({preventDefault(){}});
 const history=['2026-09-04','2026-09-08','2026-09-10'].map((date,index)=>({date,price:100+index,ma_7:null,ma_25:null,bollinger_lower:null,bollinger_middle:null,bollinger_upper:null,break_before:index===2}));
 s.answer(0,{asset:{name:'Sample',symbol:'ABC',exchange:'XNYS'},window:{observations:3,expected_sessions:4,start:'2026-09-04',end:'2026-09-10',missing_sessions:['2026-09-09']},history,indicators:null,limitations:[]});
 await pending;
 const nodes=descendants(s.elements['stock-results']);
 const path=nodes.find(n=>n.tag==='path');
 assert.equal((path.d.match(/M/g)||[]).length,2);
 assert.match(s.elements['stock-results'].textContent,/exchange session/);
 assert.match(s.elements['stock-results'].textContent,/1 requested sessions unavailable 2026-09-09/);
 assert.match(s.elements['stock-results'].textContent,/Indicators unavailable/);
 assert.equal(s.requests.length,1);
});

test('restore previews first, requires acknowledgment, and clears draft after conflict',async()=>{
 const s=setup(); const file=s.elements['restore-file'];
 file.files=[{size:2,text:async()=>'{}'}];
 const preview=s.elements['restore-preview'].listeners.click();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(s.requests[0].url,'/v1/holdings/restore/preview');
 s.answer(0,{version:'a'.repeat(64),added:[],updated:[],removed:['bitcoin'],holdings:[]}); await preview;
 assert.match(s.elements['restore-details'].textContent,/bitcoin/);
 await s.elements['restore-apply'].listeners.click(); assert.equal(s.requests.length,1);
 s.elements['restore-agree'].checked=true; s.elements['restore-agree'].listeners.change();
 const restore=s.elements['restore-apply'].listeners.click();
 assert.deepEqual(JSON.parse(s.requests[1].options.body),{content:'{}',version:'a'.repeat(64)});
 s.answer(1,{},409); await restore;
 assert.match(s.elements['restore-status'].textContent,/changed/);
 assert.equal(s.elements['restore-apply'].disabled,true);
});

test('changing the backup file discards an in-flight preview',async()=>{
 const s=setup(); s.elements['restore-file'].files=[{size:2,text:async()=>'{}'}];
 const pending=s.elements['restore-preview'].listeners.click();
 await new Promise(resolve=>setImmediate(resolve));
 s.elements['restore-file'].listeners.change();
 s.answer(0,{version:'a'.repeat(64),added:[],updated:[],removed:['bitcoin'],holdings:[]}); await pending;
 assert.equal(s.elements['restore-details'].textContent,'');
 assert.equal(s.elements['restore-apply'].disabled,true);
});

test('alerts save explicitly, check once and render safe readable results',async()=>{
 const s=setup(); assert.equal(s.requests.length,0);
 s.elements['alert-coin'].value='bitcoin'; s.elements['alert-threshold'].value='100';
 const save=s.elements['alert-form'].listeners.submit({preventDefault(){}});
 assert.deepEqual(JSON.parse(s.requests[0].options.body),{coin_id:'bitcoin',alert_type:'price',threshold:100,direction:'above'});
 const rule={id:1,coin_id:'bitcoin',alert_type:'price',threshold:100,direction:'above',is_active:1,last_triggered:null};
 s.answer(0,{alerts:[rule],events:[]}); await save;
 assert.match(s.elements['alerts-list'].textContent,/bitcoin/);
 const pending=s.elements['alerts-check'].listeners.click(); await s.elements['alerts-check'].listeners.click();
 assert.equal(s.requests.length,2);
 s.answer(1,{alerts:[rule],events:[],results:[{id:1,status:'already_matching',value:101}]}); await pending;
 assert.match(s.elements['alerts-list'].textContent,/duplicate suppressed/);
 assert.match(s.elements['alerts-status'].textContent,/No further checks/);
 const pause=s.elements['alerts-list'].children[0].children[2].listeners.click();
 assert.equal(s.requests[2].options.method,'PATCH');
 s.answer(2,{alerts:[{...rule,is_active:0}],events:[]}); await pause;
 assert.match(s.elements['alerts-list'].textContent,/Paused/);
});

test('invalid RSI alert stays local and removal needs a second click',async()=>{
 const s=setup(); s.elements['alert-coin'].value='bitcoin'; s.elements['alert-type'].value='rsi'; s.elements['alert-threshold'].value='101';
 await s.elements['alert-form'].listeners.submit({preventDefault(){}}); assert.equal(s.requests.length,0);
 const load=s.elements['alerts-load'].listeners.click();
 s.answer(0,{alerts:[{id:1,coin_id:'bitcoin',alert_type:'price',threshold:100,direction:'above',is_active:1}],events:[]}); await load;
 const card=s.elements['alerts-list'].children[0]; card.children[3].listeners.click();
 assert.equal(s.requests.length,1); assert.equal(card.children[4].hidden,false);
 card.children[5].listeners.click(); assert.equal(card.children[4].hidden,true);
});

test('backup downloads saved data on explicit click and releases the object URL',async()=>{
 const s=setup(); assert.equal(s.requests.length,0);
 s.elements['holding-amount'].value='999';
 const click=()=>s.elements['holdings-export'].listeners.click();
 const pending=click(); await click(); assert.equal(s.requests.length,1);
 assert.equal(s.requests[0].url,'/v1/holdings/export'); assert.equal(s.requests[0].options,undefined);
 const content='{"bitcoin":{"amount":2,"avg_buy_price":100}}';
 s.requests[0].resolve({ok:true,text:async()=>content}); await pending;
 assert.equal(s.downloads[0].name,'portfolio-backup.json');
 assert.equal(await s.objectUrls[0].text(),content);
 assert.match(s.elements['backup-status'].textContent,/download requested/);
 assert.equal(s.elements['holdings-export'].disabled,false);
 s.timers[0](); assert.deepEqual(s.revokedUrls,['blob:sample']);
});

test('failed export never downloads an error file and permits retry',async()=>{
 const s=setup(); const pending=s.elements['holdings-export'].listeners.click();
 s.answer(0,{error:{message:'private detail'}},503); await pending;
 assert.equal(s.downloads.length,0);
 assert.match(s.elements['backup-status'].textContent,/Could not download/);
 assert.doesNotMatch(s.elements['backup-status'].textContent,/private detail/);
 const retry=s.elements['holdings-export'].listeners.click();
 s.requests[1].resolve({ok:true,text:async()=>'not JSON'}); await retry;
 assert.equal(s.downloads.length,0);
});

test('removal reviews saved values, can cancel, and sends only the confirmed coin once',async()=>{
 const s=setup(); const load=s.elements['holdings-load'].listeners.click();
 s.answer(0,{version:'a'.repeat(64),holdings:[{coin_id:'bitcoin',amount:2,average_buy_price_usd:100}]}); await load;
 const [remove, review]=s.elements['holdings-form'].children;
 assert.equal(remove.disabled,true);
 s.elements['holdings-existing'].value='bitcoin'; s.elements['holdings-existing'].listeners.change();
 remove.listeners.click(); assert.equal(s.requests.length,1);
 assert.match(review.textContent,/bitcoin.*Saved quantity: 2/);
 review.children[2].listeners.click(); assert.equal(review.hidden,true);
 remove.listeners.click();
 const pending=review.children[1].listeners.click(); await review.children[1].listeners.click();
 assert.equal(s.requests.length,2); assert.equal(s.requests[1].options.method,'DELETE');
 assert.deepEqual(JSON.parse(s.requests[1].options.body),{coin_id:'bitcoin',version:'a'.repeat(64)});
 s.answer(1,{version:'b'.repeat(64),holdings:[]}); await pending;
 assert.match(s.elements['holdings-status'].textContent,/Removed bitcoin/);
 assert.equal(remove.disabled,true); assert.equal(review.hidden,true);
 assert.equal(s.elements['holding-coin'].value,'');
});

test('removal conflict requires reload and closes confirmation',async()=>{
 const s=setup(); const load=s.elements['holdings-load'].listeners.click();
 s.answer(0,{version:'a'.repeat(64),holdings:[{coin_id:'bitcoin',amount:1,average_buy_price_usd:null}]}); await load;
 const [remove,review]=s.elements['holdings-form'].children;
 s.elements['holdings-existing'].value='bitcoin'; s.elements['holdings-existing'].listeners.change();
 remove.listeners.click(); const pending=review.children[1].listeners.click();
 s.answer(1,{},409); await pending;
 assert.match(s.elements['holdings-status'].textContent,/changed elsewhere/);
 assert.equal(s.elements['holding-save'].disabled,true); assert.equal(remove.disabled,true);
 await review.children[1].listeners.click(); assert.equal(s.requests.length,2);
});

test('holding editor saves explicit totals, locks duplicate saves and handles conflicts',async()=>{
 const s=setup(); assert.equal(s.requests.length,0);
 const load=s.elements['holdings-load'].listeners.click();
 s.answer(0,{version:'a'.repeat(64),holdings:[]}); await load;
 s.elements['holding-coin'].value='bitcoin'; s.elements['holding-amount'].value='2'; s.elements['holding-cost'].value='50';
 const submit=()=>s.elements['holdings-form'].listeners.submit({preventDefault(){}});
 const pending=submit(); await submit(); assert.equal(s.requests.length,2);
 assert.deepEqual(JSON.parse(s.requests[1].options.body),{coin_id:'bitcoin',amount:2,avg_buy_price:50,version:'a'.repeat(64)});
 assert.equal(s.requests[1].options.method,'PUT');
 s.answer(1,{version:'b'.repeat(64),holdings:[]}); await pending;
 assert.match(s.elements['holdings-status'].textContent,/Saved bitcoin/);
 assert.match(s.elements['portfolio-status'].textContent,/Holdings changed/);
 const conflict=submit(); s.answer(2,{},409); await conflict;
 assert.equal(s.elements['holding-save'].disabled,true);
 assert.match(s.elements['holdings-status'].textContent,/changed elsewhere/);
 await submit(); assert.equal(s.requests.length,3);
});

test('holding editor rejects zero and does not retry uncertain writes',async()=>{
 const s=setup(); const load=s.elements['holdings-load'].listeners.click();
 s.answer(0,{version:'a'.repeat(64),holdings:[]}); await load;
 s.elements['holding-coin'].value='bitcoin'; s.elements['holding-amount'].value='0'; s.elements['holding-cost'].value='0';
 const submit=()=>s.elements['holdings-form'].listeners.submit({preventDefault(){}});
 await submit(); assert.equal(s.requests.length,1);
 s.elements['holding-amount'].value='1'; const pending=submit();
 s.requests[1].reject(new Error('private')); await pending;
 assert.match(s.elements['holdings-status'].textContent,/could not be confirmed/);
 assert.equal(s.elements['holding-save'].disabled,true);
});

test('portfolio loads explicitly, blocks duplicate clicks and labels partial totals',async()=>{
 const s=setup(); assert.equal(s.requests.length,0);
 const click=()=>s.elements['portfolio-load'].listeners.click();
 const pending=click(); await click(); assert.equal(s.requests.length,1);
 assert.equal(s.requests[0].url,'/v1/portfolio');
 s.answer(0,{holdings:[{coin_id:'bitcoin',amount:2,average_buy_price_usd:null,price_usd:100,value_usd:200,unrealized_pnl_usd:null,price_status:'current',price_updated_at_utc:'2026-09-25T12:00:00Z',allocation_pct:100}],priced_holdings:1,total_holdings:2,complete:false,fetched_at_utc:'2026-09-25',total_value_usd:null,priced_value_usd:200,unrealized_pnl_usd:null,limitations:[]});
 await pending;
 assert.match(s.elements['portfolio-status'].textContent,/Partial valuation/);
 assert.match(s.elements['portfolio-results'].textContent,/Allocation of priced holdings only/);
 assert.match(s.elements['portfolio-results'].textContent,/Unavailable/);
 assert.equal(s.elements['portfolio-load'].disabled,false);
 const reload=click(); assert.equal(s.elements['portfolio-results'].textContent,'');
 s.requests[1].reject(new Error('private details')); await reload;
 assert.doesNotMatch(s.elements['portfolio-status'].textContent,/private details/);
 assert.match(s.elements['portfolio-status'].textContent,/No holdings were changed/);
});

test('tiny holdings and prices are not displayed as zero',async()=>{
 const s=setup(); const pending=s.elements['portfolio-load'].listeners.click();
 s.answer(0,{holdings:[{coin_id:'tiny-coin',amount:1e-9,average_buy_price_usd:null,price_usd:1e-10,value_usd:1e-19,unrealized_pnl_usd:null,price_status:'current',price_updated_at_utc:'2026-09-27',allocation_pct:100}],priced_holdings:1,total_holdings:1,complete:true,fetched_at_utc:'2026-09-27',total_value_usd:1e-19,priced_value_usd:1e-19,unrealized_pnl_usd:null,limitations:[]}); await pending;
 assert.match(s.elements['portfolio-results'].textContent,/1e-9/);
 assert.match(s.elements['portfolio-results'].textContent,/1\.000e-10/);
});

test('empty portfolio explains how to add holdings',async()=>{
 const s=setup(); const pending=s.elements['portfolio-load'].listeners.click();
 s.answer(0,{holdings:[]}); await pending;
 assert.match(s.elements['portfolio-status'].textContent,/No saved holdings/);
 assert.equal(s.elements['portfolio-load'].disabled,false);
});

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
 test('connection failure normalized: '+message,async()=>{const s=setup();const p=s.click();s.requests[0].reject(new TypeError(message));await p;assert.match(s.elements.ai.textContent,/Could not connect to the service/);assert.equal(s.elements.recommend.disabled,false);assert.equal(s.requests.length,1);});
}

function descendants(n) { return [n,...n.children.flatMap(descendants)]; }
function chartPoints() { return ['2026-09-01','2026-09-02','2026-09-04'].map((date,i)=>({date,price:100,ma_7:i?100:null,ma_25:null,bollinger_lower:null,bollinger_middle:null,bollinger_upper:null})); }
test('chart preserves gaps, handles flat values, and offers keyboard inspection',async()=>{const s=setup();const p=s.analyze();s.answer(0,{...evidence(100),history:chartPoints()});await p;const nodes=descendants(s.elements.analysis);const paths=nodes.filter(n=>n.tag==='path');assert.equal((paths[0].d.match(/M/g)||[]).length,2);assert.doesNotMatch(paths[0].d,/NaN|Infinity/);const slider=nodes.find(n=>n.type==='range');slider.value='0';slider.listeners.input();assert.match(s.elements.analysis.textContent,/2026-09-01 UTC/);assert.match(s.elements.analysis.textContent,/Chart data table/);const bands=nodes.filter(n=>n.type==='checkbox')[1];bands.checked=true;bands.listeners.change();assert.equal(descendants(s.elements.analysis).filter(n=>n.tag==='path').length,4);});
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

for (const page of ['index','stocks','crypto','watchlist','portfolio','backups','alerts']) {
 test(`${page} page scripts initialize with only their own elements`,()=>{
  const html=fs.readFileSync(path.join(__dirname,`../static/${page}.html`),'utf8');
  const elements=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element()]));
  const events={};
  const context={Intl,URLSearchParams,window:{location:{search:'?coin=ethereum'},addEventListener:(name,fn)=>events[name]=fn},localStorage:{getItem:()=>null,setItem:()=>{}},document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},fetch:()=>assert.fail('Unexpected automatic request')};
  for(const match of html.matchAll(/src="\/assets\/([^"/]+)"/g)) vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/assets',match[1]),'utf8'),context);
  if(page==='crypto') assert.equal(elements.coin.value,'ethereum');
  if(page==='watchlist') {
   elements['watchlist-coin'].value='bitcoin';elements['watchlist-add'].listeners.click();
   assert.equal(elements['watchlist-items'].children[0].children[0].href,'/crypto.html?coin=bitcoin');
  }
 });
}

test('chart starts with price only and keeps raw values inside collapsed tools',async()=>{const s=setup();const p=s.analyze();s.answer(0,{...evidence(100),history:chartPoints()});await p;const nodes=descendants(s.elements.analysis);assert.equal(nodes.filter(n=>n.tag==='path').length,1);const tools=nodes.find(n=>n.className==='chart-tools');assert.ok(tools);assert.ok(!tools.open);assert.ok(!descendants(tools).some(n=>n.type==='range'));assert.ok(nodes.some(n=>n.type==='range'));});
require('./charts.test.cjs');
require('./account.test.cjs');
require('./account-research.test.cjs');
require('./account-assessment.test.cjs');
require('./equities.test.cjs');
require('./workspace.test.cjs');
test('chart navigation clamps endpoints and zoom does not fetch new data',async()=>{
 const s=setup();const p=s.analyze();const points=['2026-01-01','2026-05-01','2026-09-01','2026-09-04'].map((date,i)=>({...chartPoints()[0],date,price:100+i}));s.answer(0,{...evidence(100),history:points});await p;
 const nodes=descendants(s.elements.analysis),slider=nodes.find(n=>n.type==='range'),previous=nodes.find(n=>n.textContent==='← Previous'),next=nodes.find(n=>n.textContent==='Next →'),latest=nodes.find(n=>n.textContent==='Latest'),zoom=nodes.find(n=>n.tag==='select'&&n.children.some(c=>c.value==='all'));
 assert.equal(next.disabled,true);previous.listeners.click();assert.equal(slider.value,'2');
 slider.value='0';slider.listeners.input();assert.equal(previous.disabled,true);
 previous.listeners.click();assert.equal(slider.value,'0');
 zoom.value='30';zoom.listeners.change();assert.equal(slider.min,'2');assert.equal(slider.value,'2');
 latest.listeners.click();assert.equal(slider.value,'3');assert.equal(s.requests.length,1);
 assert.match(slider['aria-valuetext'],/2026-09-04/);
});
for(const page of ['index','stocks','crypto','watchlist','portfolio','alerts','backups']) test(`${page} has unique IDs and loads each script once`,()=>{
 const html=fs.readFileSync(path.join(__dirname,`../static/${page}.html`),'utf8');
 const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
 const scripts=[...html.matchAll(/\bsrc="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(new Set(ids).size,ids.length);
 assert.equal(new Set(scripts).size,scripts.length);
});
test('price labels retain small nonzero values and show unavailable values honestly',()=>{
 const context={Intl,document:{getElementById(){},createElement(){}}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/assets/common.js'),'utf8'),context);
 assert.equal(vm.runInNewContext('priceLabel(141.371736)',context),'$141.37');
 assert.equal(vm.runInNewContext('priceLabel(0.000000123456)',context),'$0.000000123456');
 assert.equal(vm.runInNewContext('priceLabel(null)',context),'N/A');
});

 test('stock listings load on page readiness without history or AI requests',async()=>{const s=setup();const p=s.documentEvents.DOMContentLoaded();assert.equal(s.requests.length,1);assert.match(s.requests[0].url,/v1.assets/);s.answer(0,{assets:[]});await p;assert.equal(s.requests.length,1);});

test('rapid listing selections load only the latest queued chart and never AI',async()=>{const s=setup();const load=s.elements['stock-load'].listeners.click();s.answer(0,{assets:[{id:'a',name:'A',symbol:'A',exchange:'XNYS'},{id:'b',name:'B',symbol:'B',exchange:'XNYS'}]});await load;s.elements['stock-options'].value='a';const first=s.elements['stock-options'].listeners.change();s.elements['stock-options'].value='b';s.elements['stock-options'].listeners.change();assert.equal(s.requests.length,2);s.answer(1,{error:{}},503);await first;assert.equal(s.requests.length,3);assert.match(s.requests[2].url,/asset_id=b/);s.answer(2,{error:{}},503);await new Promise(r=>setImmediate(r));assert.equal(s.requests.length,3);});

test('stock budget errors expose server retry time without starting a retry',async()=>{const context={document:{getElementById:()=>null},fetch:async()=>({ok:false,status:503,headers:{get:()=> '37'},json:async()=>({error:{code:'stock_budget'}})})};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/assets/common.js'),'utf8'),context);await assert.rejects(vm.runInNewContext("request('/v1/stock-analysis')",context),error=>error.retryAfterSeconds===37&&/Retry in 37 seconds/.test(error.message));});

test('alphabetical stock browsing and selection summaries reuse the loaded catalog',async()=>{const s=setup();const p=s.elements['stock-load'].listeners.click();s.answer(0,{assets:[{id:'a',name:'Alpha Company',symbol:'AAA',exchange:'XNYS',currency:'USD',asset_class:'stock'},{id:'b',name:'Beta Fund',symbol:'BBB',exchange:'ARCX',currency:'USD',asset_class:'etf'}]});await p;s.elements['stock-initial'].value='B';s.elements['stock-initial'].listeners.change();assert.equal(s.elements['stock-options'].children.length,2);assert.equal(s.requests.length,1);s.elements['stock-options'].value='b';const chart=s.elements['stock-options'].listeners.change();assert.match(s.elements['stock-listing-summary'].textContent,/Exchange-traded fund/);assert.match(s.elements['stock-listing-summary'].textContent,/holdings, fees and objective are not included/);s.answer(1,{error:{}},503);await chart;s.elements['stock-reset-filters'].listeners.click();assert.equal(s.elements['stock-initial'].value,'');assert.equal(s.elements['stock-options'].children.length,3);});

require('./listing-discovery.test.cjs');

test('history range changes update analysis and coalesce to the latest selected range',async()=>{const s=setup();const p=s.elements['stock-load'].listeners.click();s.answer(0,{assets:[{id:'a',name:'Alpha',symbol:'A',exchange:'XNYS'}]});await p;s.elements['stock-options'].value='a';s.elements['stock-period'].value='30';const first=s.elements['stock-period'].listeners.change();assert.match(s.requests[1].url,/days=30/);s.elements['stock-period'].value='366';s.elements['stock-period'].listeners.change();assert.equal(s.requests.length,2);s.answer(1,{error:{}},503);await first;assert.match(s.requests[2].url,/days=366/);s.answer(2,{error:{}},503);await new Promise(r=>setImmediate(r));assert.equal(s.requests.length,3);});
test('failed catalog loads have a visible manual retry even when Filters is closed',async()=>{const s=setup();let p=s.elements['stock-load'].listeners.click();s.answer(0,{error:{}},503);await p;assert.equal(s.elements['stock-retry'].hidden,false);p=s.elements['stock-retry'].listeners.click();assert.equal(s.elements['stock-retry'].hidden,true);s.answer(1,{assets:[]});await p;assert.equal(s.requests.length,2);});

test('Compare selections never start a hidden standalone analysis request',async()=>{const s=setup();s.setView('compare');const p=s.elements['stock-load'].listeners.click();s.answer(0,{assets:[{id:'a',name:'Alpha',symbol:'A',exchange:'XNYS'}]});await p;s.elements['stock-options'].value='a';await s.elements['stock-options'].listeners.change();s.elements['stock-period'].value='30';await s.elements['stock-period'].listeners.change();await s.elements['stock-form'].listeners.submit({preventDefault(){}});assert.equal(s.requests.length,1);});

require('./company-profile.test.cjs');

require('./research-tools.test.cjs');


test('rapid search input coalesces and still finds listings outside the rendered page',async()=>{
 const s=setup(new Map(),true),pending=s.elements['stock-load'].listeners.click();const assets=Array.from({length:500},(_,i)=>({id:`asset-${i}`,name:`Company ${String(i).padStart(3,'0')}`,symbol:`T${i}`,exchange:'XNYS',currency:'USD'}));s.answer(0,{assets,stale:false});await pending;
 assert.equal(s.elements['stock-options'].children.length,201);
 s.elements['stock-search'].value='Company 3';s.elements['stock-search'].listeners.input();
 s.elements['stock-search'].value='Company 499';s.elements['stock-search'].listeners.input();
 assert.equal(s.elements['stock-options'].disabled,true);assert.equal(s.requests.length,1);
 for(const fn of s.timers)if(!fn.cancelled)fn();
 assert.equal(s.elements['stock-options'].disabled,false);assert.equal(s.elements['stock-options'].children.length,2);assert.match(s.elements['stock-options'].children[1].textContent,/Company 499/);assert.equal(s.requests.length,1);
});

require('./screening-feed.test.cjs');

require('./request.test.cjs');

test('direct demo ETF links load the ETF catalog rather than stocks',async()=>{
 const s=setup(new Map(),false,{demo:true,search:'?asset=demo%3Aetf%3AARCX%3AUSD%3ASIMFND'});
 assert.equal(s.elements['stock-kind'].value,'etf');
 const pending=s.elements['stock-load'].listeners.click();
 assert.equal(s.requests[0].url,'/v1/assets?asset_class=etf');
 s.answer(0,{assets:[]});await pending;
});
