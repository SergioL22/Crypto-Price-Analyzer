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
 const names=['equity-list','equity-status','equity-save','equity-save-status','stock-options','equity-holding','equity-holding-form','equity-quantity','equity-cost','equity-remove-holding','equity-value','equity-valuation','equity-holdings','equity-alert-listing','equity-alert-type','equity-alert-direction','equity-alert-threshold','equity-alert-form','equity-alerts','equity-check','equity-check-result','equity-restore-file','equity-restore-preview','equity-restore-apply','screen-list','screen-status','screen-results','screen-order','screen-add','screen-run'];
 const elements=Object.fromEntries(names.map(n=>[n,new E()])),storage=new Map([[key,JSON.stringify(initial)]]),requests=[];
 const context={Intl,Date,Set,Map,JSON,Number,Array,window:{addEventListener(){},confirm:()=>true},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},document:{getElementById:n=>elements[n],createElement:()=>new E()},fetch:(url)=>new Promise(resolve=>requests.push({url,resolve}))};
 for(const name of ['common.js',file])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/assets',name),'utf8'),context);
 const picker=elements['stock-options'];picker.value=id;const option=new E();option.value=id;option.textContent='Example';picker.append(option);
 return {e:elements,storage,requests,answer:(i,data)=>requests[i].resolve({ok:true,json:async()=>data}),data:()=>JSON.parse(storage.get(key))};
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
