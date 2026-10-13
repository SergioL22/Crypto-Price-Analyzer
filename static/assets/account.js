"use strict";
(() => {
 const $=id=>document.getElementById(id),node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 let config=null,account=null,state=null,preview=null,busy=false,epoch=0,importVersion=0;
 function say(text){$('status').textContent=text;}
 function clearPreview(){preview=null;$('import-preview').replaceChildren();$('import-preview').hidden=true;$('confirm-import').checked=false;$('apply').disabled=true;}
 function signedOut(){epoch++;importVersion++;account=null;state=null;clearPreview();$('signedin').hidden=true;$('signin').hidden=false;$('account-name').textContent='';$('revision').textContent='';for(const id of ['listings','holdings','alerts','counts','holding-asset','alert-asset'])$(id).replaceChildren();for(const id of ['quantity','threshold','import-file'])$(id).value='';$('cost').value='0';}
 function controls(){for(const n of document.querySelectorAll('[data-action]'))n.disabled=busy; $('apply').disabled=busy||!preview||!$('confirm-import').checked;}
 async function request(url,options={}){
  const headers={'Content-Type':'application/json',...(account?{'X-CSRF-Token':account.csrf_token}:{}),...options.headers};
  const response=await fetch(url,{credentials:'same-origin',...options,headers});
  let body;try{body=await response.json();}catch{throw Error('The account service returned an unreadable response.');}
  if(!response.ok){if(response.status===401)signedOut();const error=Error(body.error?.message||'The request failed. Reload before trying again.');error.status=response.status;throw error;}return body;
 }
 async function perform(action){if(busy)return;busy=true;controls();try{await action();}catch(error){say(error.message);}finally{busy=false;controls();}}
 function label(id){return state?.workspace.listings.find(a=>a.id===id)?.name||id.split(':').at(-1);}
 function render(){
  if(!account||!state)return;
  $('signin').hidden=true;$('signedin').hidden=false;$('account-name').textContent=account.name;$('revision').textContent=`Saved workspace · revision ${state.revision}`;
  $('counts').replaceChildren();
  for(const [key,title]of [['listings','Saved assets'],['holdings','Positions'],['alerts','Alert rules']]){const card=node('article');card.append(node('strong',String(state.workspace[key].length)),node('span',title));$('counts').append(card);}
  const ids=[...new Set([...state.workspace.listings,...state.workspace.holdings,...state.workspace.alerts].map(a=>a.id))];
  for(const id of ['holding-asset','alert-asset']){const select=$(id),previous=select.value;select.replaceChildren();const prompt=node('option','Choose a saved asset');prompt.value='';select.append(prompt);for(const value of ids){const option=node('option',label(value));option.value=value;select.append(option);}select.value=ids.includes(previous)?previous:'';}
  for(const [key,target]of [['listings','listings'],['holdings','holdings'],['alerts','alerts']]){
   $(target).replaceChildren();
   state.workspace[key].forEach((item,index)=>{const row=node('li',key==='listings'?item.name:key==='holdings'?`${label(item.id)} · ${item.quantity} shares · average cost $${item.cost}`:`${label(item.id)} · ${item.type} ${item.direction} ${item.threshold} · saved rule, not monitored`);
    const remove=node('button',key==='listings'?'Remove from watchlist':key==='holdings'?'Remove position':'Remove rule');remove.type='button';remove.className='secondary';remove.setAttribute('data-action','');
    remove.addEventListener('click',()=>{if(!remove._confirmed){remove._confirmed=true;remove.textContent='Confirm removal';return;}perform(async()=>{const data=structuredClone(state.workspace);data[key].splice(index,1);await save(data);});});
    row.append(remove);$(target).append(row);});
   if(!state.workspace[key].length)$(target).append(node('li',key==='listings'?'No saved assets yet.':key==='holdings'?'No positions saved.':'No alert rules saved.'));
  }
  controls();
 }
 async function load(){const current=epoch;const data=await request('/v2/workspace');if(current!==epoch)return;state=data;clearPreview();render();say('Your saved workspace is ready.');}
 async function save(data){const current=epoch;const response=await request('/v2/workspace',{method:'PUT',body:JSON.stringify({revision:state.revision,workspace:data})});if(current!==epoch)return;state=response;clearPreview();render();say('Changes saved to your account.');}
 async function login(profile){say('Opening sample account…');await request('/auth/demo',{method:'POST',body:JSON.stringify({profile})});epoch++;account=await request('/v2/session');await load();}
 for(const name of ['avery','sam'])$(name).addEventListener('click',()=>perform(()=>login(name)));
 $('reload').addEventListener('click',()=>perform(load));
 $('logout').addEventListener('click',()=>perform(async()=>{await request('/auth/logout',{method:'POST'});signedOut();say('Signed out. Your server workspace is preserved.');}));
 $('listing-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{const select=$('asset'),id=select.value,data=structuredClone(state.workspace);if(data.listings.some(a=>a.id===id)){say('This asset is already saved.');return;}data.listings.push({id,name:select.options[select.selectedIndex].textContent});await save(data);});});
 $('holding-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{const id=$('holding-asset').value,quantity=Number($('quantity').value),cost=Number($('cost').value);if(!id||!Number.isFinite(quantity)||quantity<=0||!Number.isFinite(cost)||cost<0){say('Choose an asset, positive shares and a nonnegative average cost.');return;}const data=structuredClone(state.workspace),holding={id,quantity,cost},index=data.holdings.findIndex(h=>h.id===id);if(index<0)data.holdings.push(holding);else data.holdings[index]=holding;await save(data);});});
 $('alert-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{const id=$('alert-asset').value,type=$('alert-type').value,threshold=Number($('threshold').value);if(!id||!Number.isFinite(threshold)||threshold<0||type==='rsi'&&threshold>100){say('Choose an asset and valid threshold; RSI must be from 0 to 100.');return;}const data=structuredClone(state.workspace);data.alerts.push({id,type,direction:$('direction').value,threshold,triggered:false});await save(data);});});
 $('import-file').addEventListener('change',()=>{importVersion++;clearPreview();controls();});
 $('preview').addEventListener('click',()=>perform(async()=>{
  clearPreview();const file=$('import-file').files[0],generation=importVersion,current=epoch;
  if(!file||file.size>500000){say('Choose a stock workspace JSON file under 500 KB.');return;}
  let data;try{data=JSON.parse(await file.text());}catch{say('The file is not valid JSON. Nothing imported.');return;}
  if(generation!==importVersion||current!==epoch)return;
  const result=await request('/v2/import/preview',{method:'POST',body:JSON.stringify(data)});
  if(generation!==importVersion||current!==epoch)return;
  preview=result;const panel=$('import-preview');panel.hidden=false;panel.append(node('h3',`Destination: ${result.destination.name}`),node('p',`Account ID: ${result.destination.account_id}`),node('p',`Incoming: ${result.incoming.listings} assets, ${result.incoming.holdings} positions, ${result.incoming.alerts} rules.`),node('p',`Replaces: ${result.existing.listings} assets, ${result.existing.holdings} positions, ${result.existing.alerts} rules. Preview expires in 10 minutes.`));
  for(const listing of result.workspace.listings)panel.append(node('p',listing.name));
  const importedLabel=id=>result.workspace.listings.find(a=>a.id===id)?.name||id.split(':').at(-1);
  for(const holding of result.workspace.holdings)panel.append(node('p',`${importedLabel(holding.id)} · ${holding.quantity} shares · average cost $${holding.cost}`));
  for(const alert of result.workspace.alerts)panel.append(node('p',`${importedLabel(alert.id)} · ${alert.type} ${alert.direction} ${alert.threshold} · saved rule, not monitored`));
  say('Preview ready. Review the account and replacement counts before confirming.');
 }));
 $('confirm-import').addEventListener('change',controls);
 $('cancel-import').addEventListener('click',()=>perform(async()=>{importVersion++;clearPreview();await request('/v2/import/preview',{method:'DELETE'});say('Preview canceled. Nothing imported.');}));
 $('apply').addEventListener('click',()=>perform(async()=>{if(!preview||!$('confirm-import').checked)return;const current=epoch;try{const result=await request('/v2/import/confirm',{method:'POST',body:JSON.stringify({token:preview.token,confirm:true})});if(current!==epoch)return;state=result;clearPreview();render();say('Import complete. Your original file was not changed.');}catch(error){clearPreview();throw error;}}));
 $('export').addEventListener('click',()=>perform(async()=>{const data=await request('/v2/export'),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),link=node('a');link.href=url;link.download='account-workspace.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);say('Backup downloaded. Keep your positions private.');}));
 async function initialize(){try{config=await request('/v2/config');$('mode').textContent=config.demo?'SAMPLE STAGING · no live data':'ACCOUNT WORKSPACE · market data not enabled';$('demo-login').hidden=!config.demo;$('managed-login').hidden=config.demo;$('signin-note').textContent=config.demo?'These named sample profiles demonstrate separate workspaces. They are not real authentication and are available only on loopback.':'Your identity provider handles sign-in and account recovery. This app does not store your password.';try{account=await request('/v2/session');await load();}catch(error){if(error.status===401){signedOut();say(config.demo?'Choose a sample account to explore.':'Sign in securely to open your workspace.');}else throw error;}}catch(error){say(error.message);}}
 initialize();
})();
