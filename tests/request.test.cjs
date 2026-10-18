const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function setup(fetch){
 const timers=[],cleared=[];
 const context={fetch,AbortController,Intl,setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length;},clearTimeout:id=>cleared.push(id)};
 vm.createContext(context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/assets/common.js'),'utf8'),context);
 return {request:(...args)=>context.request(...args),timers,cleared};
}
test('a stalled read times out, aborts, and never retries',async()=>{
 let calls=0,signal;const s=setup((_,opts)=>{calls++;signal=opts.signal;return new Promise(()=>{});});
 const pending=s.request('/v1/assets');
 assert.equal(s.timers[0].ms,75000);s.timers[0].fn();
 await assert.rejects(pending,/Loading took too long/);
 assert.equal(signal.aborted,true);assert.equal(calls,1);assert.deepEqual(s.cleared,[1]);
});
test('a stalled response body is also bounded',async()=>{
 const s=setup(async()=>({ok:true,json:()=>new Promise(()=>{})}));
 const pending=s.request('/v1/assets');await Promise.resolve();s.timers[0].fn();
 await assert.rejects(pending,/Loading took too long/);
});
test('completed reads clear the deadline and retain caller options',async()=>{
 let options;const s=setup(async(_,opts)=>{options=opts;return {ok:true,json:async()=>({assets:[]})};});
 assert.deepEqual(await s.request('/v1/assets',{headers:{Accept:'application/json'}}),{assets:[]});
 assert.equal(options.headers.Accept,'application/json');assert.deepEqual(s.cleared,[1]);
});
test('offline errors describe the hosted service and expose no underlying detail',async()=>{
 const s=setup(async()=>{throw new Error('private internal address');});
 await assert.rejects(s.request('/v1/assets'),error=>/Check your connection/.test(error.message)&&! /local server|private internal/.test(error.message));
 assert.deepEqual(s.cleared,[1]);
});
test('explicit mutation requests are not aborted or retried by the read deadline',async()=>{
 let calls=0;const s=setup(async()=>{calls++;return {ok:true,json:async()=>({ok:true})};});
 await s.request('/v1/example',{method:'POST'});assert.equal(calls,1);assert.equal(s.timers.length,0);
});
test('caller abort signals remain effective',async()=>{
 let signal;const controller=new AbortController();
 const s=setup((_,opts)=>{signal=opts.signal;return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('abort'))));});
 const pending=s.request('/v1/assets',{signal:controller.signal});controller.abort();
 await assert.rejects(pending,/Could not connect/);assert.equal(signal.aborted,true);assert.deepEqual(s.cleared,[1]);
});
