"use strict";
// Catalog-only discovery: no HTTP, storage, market rankings or inferred sectors.
const ListingDiscovery = (() => {
 const exchanges={XNYS:'NYSE',XNAS:'Nasdaq',XNGS:'Nasdaq Global Select',XNMS:'Nasdaq Global Market',XNCM:'Nasdaq Capital Market',ARCX:'NYSE Arca',XASE:'NYSE American',BATS:'Cboe BZX',XCRY:'Crypto market'};
 const normalize=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
 const cache=new WeakMap(),collator=new Intl.Collator('en');let lastQuery='',lastTokens=[];
 function metadata(asset){const signature=`${asset.name}|${asset.symbol}|${asset.exchange}`;let value=cache.get(asset);if(!value||value.signature!==signature){const name=normalize(asset.name);value={signature,name,symbol:asset.symbol.toLowerCase(),haystack:normalize(`${asset.name} ${asset.symbol} ${asset.exchange} ${exchanges[asset.exchange]||''}`)};cache.set(asset,value);}return value;}
 function matches(asset,{query='',exact=false,exchange='',initial=''}={}){
  if(exchange&&asset.exchange!==exchange)return false;
  const info=metadata(asset),first=info.name.charAt(0);
  if(initial&&(initial==='#'?!/^[0-9]/.test(first):first!==initial.toLowerCase()))return false;
  if(!query.trim())return true;
  if(exact)return info.symbol===query.trim().toLowerCase();
  if(query!==lastQuery){lastQuery=query;lastTokens=normalize(query).split(' ').filter(Boolean);}
  return lastTokens.every(token=>info.haystack.includes(token));
 }
 function sort(assets,order='name',query=''){
  const term=query.trim().toLowerCase(),normalized=normalize(query);
  const rank=a=>!term?0:metadata(a).symbol===term?0:metadata(a).name.startsWith(normalized)?1:2;
  return [...assets].sort((a,b)=>(order==='relevance'?rank(a)-rank(b):0)||collator.compare(String(a[order==='relevance'?'name':order]||a.name),String(b[order==='relevance'?'name':order]||b.name))||collator.compare(a.name,b.name)||collator.compare(a.exchange,b.exchange));
 }
 function describe(asset){
  const type=asset.asset_class==='etf'?'Exchange-traded fund':asset.asset_class==='crypto'?'Crypto asset':'Stock listing';
  const explanation=asset.asset_class==='etf'?'A fund traded on an exchange. Its holdings, fees and objective are not included in this catalog.':asset.asset_class==='crypto'?'A crypto asset identified by its provider ID.':'A stock-market listing. The issuer business, sector and share-class details are not included in this catalog.';
  return {type,venue:exchanges[asset.exchange]||asset.exchange,text:`${asset.name} · ${asset.symbol} · ${exchanges[asset.exchange]||asset.exchange} · ${asset.currency}. ${explanation}`};
 }
 return {matches,sort,describe,exchanges};
})();
