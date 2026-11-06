'use strict';
(()=>{
 const stats=document.getElementById('sample-stats'),status=document.getElementById('sample-status');
 const pct=v=>`${(v*100).toFixed(0)}%`;
 async function get(path){const r=await fetch(path,{headers:{Accept:'application/json'}});if(!r.ok)throw new Error(String(r.status));return r.json();}
 function show(values){[...stats.querySelectorAll('dd')].forEach((dd,i)=>{dd.textContent=values[i];});}
 Promise.all([get('/v1/sec/overlap?a=SPY&b=QQQ'),get('/v1/sec/fund?symbol=VTI'),get('/v1/sec/coverage')])
  .then(([overlap,vti,coverage])=>{
   show([pct(overlap.a_weight_in_b),pct(overlap.b_weight_in_a),vti.summary.holding_count.toLocaleString('en-US'),coverage.generated_at_utc.slice(0,10)]);
   status.textContent=`ETF holdings as of ${overlap.a.period_end}, from each fund's latest Form N-PORT. In other words, about ${pct(overlap.b_weight_in_a)} of a QQQ investment is in stocks SPY also owns.`;
  })
  .catch(()=>{show(['—','—','—','—']);status.textContent='Live figures are unavailable right now. The research pages may still be waking up; try again in a minute.';});
})();
