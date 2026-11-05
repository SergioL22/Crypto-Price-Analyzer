const {test}=require('node:test');
const assert=require('node:assert/strict');
const lab=require('../static/assets/price-lab-core.js');

const CSV='Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-03,1,1,1,"1,010.00",101,5\n2024-01-02,1,1,1,1000,100,5\n2024-01-04,1,1,1,990,99,5\nbad,1,1,1,1,1,1\n';

test('parses broker-style CSV, prefers adjusted close, sorts and reports skipped rows',()=>{
 const p=lab.parseCsv(CSV);
 assert.equal(p.column,'Adj Close');assert.equal(p.skipped,1);
 assert.deepEqual(p.rows.map(r=>[r.date,r.close]),[['2024-01-02',100],['2024-01-03',101],['2024-01-04',99]]);
 assert.deepEqual(lab.parseCsv('date;price\n1/2/2024;$5\n1/3/2024;6\n').rows.map(r=>r.date),['2024-01-02','2024-01-03']);
});

test('rejects missing columns, duplicate dates and impossible dates',()=>{
 assert.throws(()=>lab.parseCsv('day,volume\n2024-01-02,1\n2024-01-03,2\n'),/Date column/);
 assert.throws(()=>lab.parseCsv('Date,Close\n2024-01-02,1\n2024-01-02,2\n'),/more than once/);
 assert.equal(lab.parseDate('2024-02-30'),null);
 assert.throws(()=>lab.parseCsv('Date,Close\n2024-02-30,1\n2024-02-31,2\n'),/Fewer than two/);
});

test('moving average and RSI follow the standard definitions',()=>{
 assert.deepEqual(lab.sma([1,2,3,4],2),[null,1.5,2.5,3.5]);
 const up=Array.from({length:20},(_,i)=>i+1);
 assert.equal(lab.rsi(up).at(-1),100);assert.equal(lab.rsi(up)[13],null);
 const flat=lab.rsi([1,2,1,2,1,2,1,2,1,2,1,2,1,2,1,2]);assert.ok(flat.at(-1)>40&&flat.at(-1)<60);
});

test('stats report return, drawdown and annualised figures only when meaningful',()=>{
 const rows=[['2020-01-01',100],['2020-06-01',150],['2021-01-01',75],['2022-01-01',121]].map(([date,close])=>({date,close}));
 const s=lab.stats(rows);
 assert.ok(Math.abs(s.total_return-0.21)<1e-12);
 assert.equal(s.max_drawdown.value,-0.5);assert.equal(s.max_drawdown.peak,'2020-06-01');assert.equal(s.max_drawdown.trough,'2021-01-01');
 assert.ok(Math.abs(s.cagr-0.1)<0.001);
 assert.equal(lab.stats(rows.slice(0,2)).cagr,null);
});

test('growth compares only on shared dates',()=>{
 const a={name:'A',rows:[{date:'d1',close:10},{date:'d2',close:20},{date:'d3',close:30}]},b={name:'B',rows:[{date:'d2',close:5},{date:'d3',close:10}]};
 const g=lab.growth([a,b],100);
 assert.deepEqual(g.dates,['d2','d3']);assert.deepEqual(g.lines.map(l=>l.values),[[100,150],[100,200]]);
});

test('simulator handles lump sums and monthly buys without inventing prices',()=>{
 const rows=[['2024-01-02',10],['2024-01-03',20],['2024-02-01',20],['2024-02-02',40]].map(([date,close])=>({date,close}));
 const lump=lab.simulate(rows,{amount:100,start:'2024-01-01'});
 assert.equal(lump.shares,10);assert.equal(lump.value,400);assert.equal(lump.first_buy,'2024-01-02');
 const monthly=lab.simulate(rows,{amount:100,start:'2024-01-03',mode:'monthly'});
 assert.equal(monthly.buys,2);assert.equal(monthly.invested,200);assert.equal(monthly.value,(5+5)*40);
 assert.throws(()=>lab.simulate(rows,{amount:100,start:'2025-01-01'}),/after the last row/);
 assert.throws(()=>lab.simulate(rows,{amount:0,start:'2024-01-01'}),/greater than zero/);
});

test('alert rules check the latest close or RSI',()=>{
 const rows=Array.from({length:20},(_,i)=>({date:`2024-01-${String(i+1).padStart(2,'0')}`,close:i+1}));
 assert.deepEqual(lab.checkRule(rows,{type:'close_above',value:15}),{latest:20,triggered:true});
 assert.equal(lab.checkRule(rows,{type:'rsi_below',value:30}).triggered,false);
 assert.equal(lab.checkRule(rows.slice(0,5),{type:'rsi_above',value:1}).latest,null);
});

test('example data is deterministic and labelled fictional',()=>{
 const a=lab.example('Fictional A',7,.08),b=lab.example('Fictional A',7,.08);
 assert.equal(a.fictional,true);assert.equal(a.rows.length,1260);assert.deepEqual(a.rows.slice(-1),b.rows.slice(-1));
});
