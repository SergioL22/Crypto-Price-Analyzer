const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class E{
 constructor(tag='div',text=''){this.tag=tag;this.text=text;this.children=[];this.listeners={};this.value='';this.disabled=false;}
 append(...children){this.children.push(...children);}replaceChildren(...children){this.text='';this.children=children;}
 set textContent(v){this.text=String(v);this.children=[];}get textContent(){return this.text+this.children.map(c=>c.textContent).join(' ');}
 addEventListener(k,fn){this.listeners[k]=fn;}setAttribute(k,v){this[k]=v;}querySelector(){return this.submit;}contains(target){return this.children.some(c=>c===target||c.contains?.(target));}
}
const id='twelvedata:stock:XNYS:USD:ABC',other=id.replace('ABC','XYZ');
function setup(simulator=false){
 const names=['simulation-form','simulation-asset','simulation-benchmark','simulation-amount','simulation-date','simulation-status','simulation-results'];
 const e=simulator?Object.fromEntries(names.map(n=>[n,new E()])):{};
 if(simulator)e['simulation-form'].submit=new E('button');
 const calls=[],charts=[],storage=new Map([['research-desk.equities.v1',JSON.stringify({listings:[{id,name:'Example'},{id:other,name:'Benchmark'}]})]]);
 const context={Date,Number,Array,JSON,Math,encodeURIComponent,$:n=>e[n],el:(tag,text)=>new E(tag,text),priceLabel:v=>'$'+v.toFixed(2),format:String,priceChart:(...args)=>charts.push(args),localStorage:{getItem:k=>storage.get(k)},request:url=>new Promise((resolve,reject)=>calls.push({url,resolve,reject}))};
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/assets/research-tools.js'),'utf8'),context);
 return {e,calls,charts,context,tools:vm.runInContext('ResearchReturns',context)};
}
function history(prices=[10,20],dates=['2026-10-14','2026-10-15']){return {history:dates.map((date,i)=>({date,price:prices[i]})),window:{latest_closed_session:dates.at(-1),missing_sessions:[]},history_source:{fetched_at_utc:'2026-10-16T00:00:00Z'}};}
test('hypothetical fractional-share arithmetic uses adjusted prices and exact endpoints',()=>{const {tools}=setup(),p=tools.series(history(),'2026-10-14'),r=tools.result(p,125);assert.equal(r.shares,12.5);assert.equal(r.value,250);assert.equal(r.percent,100);assert.equal(r.change,125);assert.throws(()=>tools.result(p,Infinity));});
test('saved date starts after saving and never invents a prelisting baseline',()=>{const {tools}=setup();assert.equal(tools.series(history(),'2026-10-14',true)[0].date,'2026-10-15');assert.throws(()=>tools.series(history(),'2025-01-01'));assert.throws(()=>tools.series(history(),'2026-10-16',true));});
test('invalid, stale, duplicate and missing sessions fail closed',()=>{const {tools}=setup();for(const mutate of [d=>d.window.latest_closed_session='2026-10-16',d=>d.window.missing_sessions=['2026-10-14'],d=>delete d.window.missing_sessions,d=>d.history[0].price=0,d=>d.history[1].date=d.history[0].date]){const d=history();mutate(d);assert.throws(()=>tools.series(d,'2026-10-14'));}});
test('future dates, invalid dates and windows beyond ten years are rejected',()=>{const {tools}=setup();assert.throws(()=>tools.days('2999-01-01'));assert.throws(()=>tools.days('2026-02-30'));assert.throws(()=>tools.days('2000-01-01'));assert.ok(tools.days('2026-10-01')>=2);});
test('watchlist loading is explicit and late responses are discarded',async()=>{const s=setup(),root=new E(),listing={id,name:'Example',saved_on:'2026-10-13'};let current=listing;s.context.watchPerformancePanel(root,listing,()=>current,()=>{});assert.equal(s.calls.length,0);const details=root.children[0],button=details.children.find(n=>n.tag==='button'),output=details.children.at(-1);const pending=button.listeners.click();current=null;s.calls[0].resolve(history());await pending;assert.doesNotMatch(output.textContent,/100.00%/);assert.equal(s.charts.length,0);});
test('watchlist performance shows change and never changes stored entries',async()=>{const s=setup(),root=new E(),listing={id,name:'Example',saved_on:'2026-10-13'};s.context.watchPerformancePanel(root,listing,()=>listing,()=>{});const pending=root.children[0].children.find(n=>n.tag==='button').listeners.click();s.calls[0].resolve(history());await pending;assert.match(root.textContent,/100.00%/);assert.match(root.textContent,/same split-adjusted/);assert.equal(s.charts.length,1);assert.equal(listing.saved_on,'2026-10-13');});
test('old watchlist entries require explicit tracking without invented dates',()=>{const s=setup(),root=new E();let started=false;s.context.watchPerformancePanel(root,{id,name:'Old'},()=>({id}),()=>started=true);assert.match(root.textContent,/no recorded save date/);root.children[0].children.find(n=>n.tag==='button').listeners.click();assert.equal(started,true);assert.equal(s.calls.length,0);});
test('simulator is manual and rejects mismatched benchmark sessions',async()=>{const s=setup(true);assert.equal(s.calls.length,0);s.e['simulation-asset'].value=id;s.e['simulation-benchmark'].value=other;s.e['simulation-amount'].value='100';s.e['simulation-date'].value='2026-10-14';const pending=s.e['simulation-form'].listeners.submit({preventDefault(){}});s.calls[0].resolve(history());await new Promise(resolve=>setImmediate(resolve));assert.equal(s.calls.length,2);s.calls[1].resolve(history([10],['2026-10-15']));await pending;assert.match(s.e['simulation-status'].textContent,/dates do not match/);assert.equal(s.e['simulation-results'].children.length,0);});
test('simulator discards changed inputs and never requests the comparison afterward',async()=>{const s=setup(true);s.e['simulation-asset'].value=id;s.e['simulation-benchmark'].value=other;s.e['simulation-amount'].value='100';s.e['simulation-date'].value='2026-10-14';const pending=s.e['simulation-form'].listeners.submit({preventDefault(){}});s.e['simulation-amount'].listeners.input();s.calls[0].resolve(history());await pending;assert.equal(s.calls.length,1);assert.equal(s.charts.length,0);assert.match(s.e['simulation-status'].textContent,/Inputs changed/);});
test('matching benchmark uses same initial amount and sessions',async()=>{const s=setup(true);s.e['simulation-asset'].value=id;s.e['simulation-benchmark'].value=other;s.e['simulation-amount'].value='100';s.e['simulation-date'].value='2026-10-14';const pending=s.e['simulation-form'].listeners.submit({preventDefault(){}});s.calls[0].resolve(history());await new Promise(resolve=>setImmediate(resolve));s.calls[1].resolve(history([10,15]));await pending;assert.match(s.e['simulation-results'].textContent,/Difference in ending value: \$50.00/);assert.match(s.e['simulation-status'].textContent,/No trade/);});


test('numeric date entry adds separators progressively and preserves date validation',()=>{
 const s=setup(true),field=s.e['simulation-date'];
 for(const [input,expected] of [['2020','2020'],['20200','2020-0'],['202001','2020-01'],['2020013','2020-01-3'],['20200131','2020-01-31'],['2020-01-31','2020-01-31']]){field.value=input;field.listeners.input();assert.equal(field.value,expected);}
 assert.equal(s.tools.typedDate('bad date'),'bad date');assert.throws(()=>s.tools.date(s.tools.typedDate('20200230')));assert.equal(s.calls.length,0);
});




test('simulator exposes one numeric calendar date field without a duplicate',()=>{const html=fs.readFileSync(path.join(__dirname,'../static/portfolio.html'),'utf8');assert.match(html,/Calendar date \(YYYY-MM-DD\)/);assert.match(html,/id="simulation-date"[^>]*inputmode="numeric"/);assert.doesNotMatch(html,/id="simulation-calendar"|Starting date \(YYYY-MM-DD\)/);});
