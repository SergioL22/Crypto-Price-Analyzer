const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
class Node{
 constructor(){this.children=[];this.value='';this.text='';this.listeners={};}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(){this.children=[];this.text='';}
 set textContent(value){this.text=String(value);this.children=[];}
 get textContent(){return this.text+' '+this.children.map(n=>n.textContent).join(' ');}
 setAttribute(){} addEventListener(name,fn){this.listeners[name]=fn;}
}
function setup(page){const root=new Node(),panel=new Node(),open=new Node(),close=new Node();panel.showModal=()=>panel.open=true;panel.close=()=>{panel.open=false;panel.listeners.close();};open.focus=()=>open.focused=true;Node.prototype.focus=function(){this.focused=true;};root.controls={panel,open,close};const context={Intl,window:{location:{pathname:page}},document:{body:{dataset:{demo:'true'}},getElementById:id=>({'beginner-help-content':root,'beginner-help':panel,'beginner-help-open':open,'beginner-help-close':close}[id]||null),createElement:()=>new Node()}};vm.createContext(context);for(const name of ['common.js','help.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/assets',name),'utf8'),context);return root;}
test('glossary explains alert thresholds and supports search with an honest empty state',()=>{
 const root=setup('/alerts.html');assert.match(root.textContent,/save the alert rule/);assert.match(root.textContent,/Fictional|fictional/);
 const search=root.children.find(n=>n.children.some(c=>c.type==='search')).children[0];search.value='threshold';search.listeners.input();assert.match(root.textContent,/greater than \$100/);assert.doesNotMatch(root.textContent,/Bollinger bands/);
 search.value='not-a-term-zz';search.listeners.input();assert.match(root.textContent,/No matching terms/);search.value='';search.listeners.input();assert.match(root.textContent,/Bollinger bands/);
});
test('each workspace page includes accessible help and the shared glossary script',()=>{
 for(const name of ['index.html','stocks.html','watchlist.html','alerts.html','portfolio.html','backups.html','crypto.html']){const html=fs.readFileSync(path.join(__dirname,'../static',name),'utf8');assert.match(html,/id="beginner-help"/);assert.match(html,/\/assets\/help.js/);assert.match(html,/Help &amp; glossary/);}
});

test('compact help opens a modal, focuses search and returns focus on close',()=>{
 const root=setup('/alerts.html'),{panel,open,close}=root.controls;
 open.listeners.click();assert.equal(panel.open,true);assert.equal(root.children.find(n=>n.children.some(c=>c.type==='search')).children[0].focused,true);
 close.listeners.click();assert.equal(panel.open,false);assert.equal(open.focused,true);
 open.listeners.click();let prevented=false;panel.listeners.keydown({key:"Escape",preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(panel.open,false);
});
