const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../static/assets/workspace.js'),'utf8');
function run(url, comparison = false) {
 const location = new URL(url,'http://localhost');
 const link = (text, href) => ({textContent:text, attrs:{href},getAttribute(k){return this.attrs[k]},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]}});
 const markets=[link('Stocks & ETFs','/'),link('Crypto','/crypto.html')];
 const pages=[link('Explore','/'),link('Portfolio','/portfolio.html'),link('Compare','/?view=compare')];
 pages[0].attrs['aria-current']='page';
 const sections=['stocks','crypto'].map(workspace=>({dataset:{workspace},hidden:false}));
 const heading={textContent:'Portfolio'};
 const body={dataset:{}};
 const document={body,querySelectorAll:s=>s==='[data-workspace]'?sections:s==='.market-nav a'?markets:pages,querySelector:s=>s==='header h1'?heading:sections[0],getElementById:()=>comparison?{}:null};
 vm.runInNewContext(source,{document,window:{location},URLSearchParams});
 return {body,markets,pages,sections,heading};
}
test('stock workspace keeps stock tools visible and stock links unscoped',()=>{
 const s=run('/portfolio.html');
 assert.equal(s.sections[0].hidden,false);assert.equal(s.sections[1].hidden,true);
 assert.equal(s.pages[1].attrs.href,'/portfolio.html');
 assert.equal(s.markets[0].attrs['aria-current'],'page');
 assert.equal(s.heading.textContent,'Stocks & ETFs · Portfolio');
});
test('crypto workspace preserves market across tool navigation',()=>{
 const s=run('/portfolio.html?market=crypto');
 assert.equal(s.sections[0].hidden,true);assert.equal(s.sections[1].hidden,false);
 assert.equal(s.pages[0].attrs.href,'/crypto.html');
 assert.equal(s.pages[1].attrs.href,'/portfolio.html?market=crypto');
 assert.equal(s.markets[1].attrs['aria-current'],'page');
});
test('comparison has its own active navigation state',()=>{
 const s=run('/?view=compare',true);
 assert.equal(s.body.dataset.view,'compare');
 assert.equal(s.pages[0].attrs['aria-current'],undefined);
 assert.equal(s.pages[2].attrs['aria-current'],'page');
});
