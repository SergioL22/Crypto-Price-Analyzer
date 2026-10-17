"use strict";
// Explicit user action only. Never included in the trading evidence/LLM snapshot.
function companyProfilePanel(root,asset,load,isCurrent){
 if(asset.asset_class!=='stock')return;
 const button=el('button','Load company details');button.type='button';button.className='secondary';
 const output=el('div');output.className='company-profile';output.setAttribute('role','status');output.setAttribute('aria-live','polite');
 root.append(button,output);let busy=false;
 const current=()=>isCurrent()&&(!root.contains||root.contains(output));
 button.addEventListener('click',async()=>{
  if(busy||!current())return;busy=true;button.disabled=true;output.replaceChildren(el('p','Loading company details...'));
  try{
   const data=await load();if(!current())return;
   if(data.asset_id!==asset.id)throw Error('Company profile does not match the selected listing.');
   output.replaceChildren();
   if(data.status!=='available'||!data.profile){output.append(el('p',data.message));return;}
   const profile=data.profile,fields=[['Company name',profile.name],['Industry (Finnhub classification)',profile.finnhub_industry],['Headquarters country',profile.headquarters_country],['Reporting currency',profile.reporting_currency],['IPO date',profile.ipo_date]];
   const values=el('dl');for(const [label,value]of fields){const row=el('div');row.append(el('dt',label),el('dd',value||'Unavailable'));values.append(row);}output.append(values);
   if(typeof profile.website_url==='string'&&/^https?:\/\//i.test(profile.website_url)){const link=el('a','Company website (external)');link.href=profile.website_url;link.target='_blank';link.rel='noopener noreferrer';output.append(link);}
   output.append(el('p',`${data.source} · retrieval request ${data.fetched_at_utc}${data.cache_hit?' · cached profile':''}.`),el('p','Matched by ticker and operating exchange; the catalog exchange segment is not independently verified. The provider does not supply a profile update timestamp.'),el('p','Business descriptions, verified sector classifications and ETF holdings/fees are not included. Missing values are not estimated.'));
  }catch(error){if(current())output.replaceChildren(el('p',error.message||'Company profile unavailable. Retry manually.'));}
  finally{busy=false;button.disabled=false;}
 });
}
