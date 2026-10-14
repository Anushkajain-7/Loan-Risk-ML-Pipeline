'use strict';
let csrf='';let currentRef='';
const $=id=>document.getElementById(id);
const status=message=>{$('status').textContent=message;};
async function api(path,method='GET',data){
  const headers={'Content-Type':'application/json'};
  if(csrf)headers['X-CSRF-Token']=csrf;
  const response=await fetch(path,{method,headers,credentials:'same-origin',...(data?{body:JSON.stringify(data)}:{})});
  const value=await response.json();
  if(!response.ok)throw new Error(`${value.message||'Request failed'}${value.correlation_id?' · reference '+value.correlation_id:''}`);
  return value;
}
function node(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function signedIn(value){$('auth-panel').hidden=!value;$('workspace').hidden=!value;$('logout').hidden=!value;document.querySelectorAll('img[data-src]').forEach(image=>{if(value)image.src=image.dataset.src;else image.removeAttribute('src');});if(!value){csrf='';currentRef='';$('history').replaceChildren();$('monitor-data').textContent='';$('batch-input').value='';$('batch-result').textContent='';$('result').replaceChildren(node('h2','Ready when you are.'));$('application').reset();}}
const fields=[
 ['amount_requested','Amount requested','number',500],['loan_duration','Duration · dataset units','number',6],
 ['monthly_income_amount','Monthly income','number',2400],['monthly_rent_amount','Monthly rent','number',600],
 ['raw_l2c_score','L2C score','number',650],['raw_FICO_telecom','FICO telecom','number',570],
 ['raw_FICO_retail','FICO retail','number',600],['raw_FICO_bank_card','FICO bank card','number',640],
 ['raw_FICO_money','FICO money','number',580],['bank_account_direct_deposit','Direct deposit',['true','false'],'true'],
 ['payment_ach','ACH payment',['true','false'],'true'],['residence_duration','Residence tenure',['3+ years','1-2 years','7-12 months','6 months or less'],'1-2 years'],
 ['bank_account_duration','Bank-account tenure',['3+ years','1-2 years','7-12 months','6 months or less'],'1-2 years'],
 ['payment_frequency','Payment frequency',['Bi-weekly','Monthly','Semi-monthly','Weekly'],'Bi-weekly']];
for(const [name,title,type] of fields){const label=node('label',title);let input;
  if(Array.isArray(type)){input=node('select');for(const option of type){const opt=node('option',option);opt.value=option;input.append(opt);}}
  else{input=node('input');input.type='number';input.step=name==='loan_duration'?'1':'any';input.min=name==='monthly_rent_amount'?'0':'1';}
  input.name=name;input.required=true;label.append(input);$('fields').append(label);
}
$('sample').onclick=()=>{for(const [name,title,type,value] of fields)$('application').elements[name].value=value;status('Synthetic example loaded. These values do not describe an actual borrower.');};
document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{document.querySelectorAll('.tab').forEach(t=>t.hidden=t.id!==button.dataset.tab);document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button));$('page-title').textContent=button.textContent.slice(5).trim();if(button.dataset.tab==='monitor')refresh();});
async function authenticate(route){try{const form=$('auth-form');if(!form.reportValidity())return;const result=await api('/api/auth/'+route,'POST',Object.fromEntries(new FormData(form)));csrf=result.csrf_token;form.reset();signedIn(true);status('Private workspace ready.');await findings();}catch(e){status(e.message);}}
$('auth-form').onsubmit=e=>{e.preventDefault();authenticate('login');};$('signup').onclick=()=>authenticate('signup');
$('logout').onclick=async()=>{try{await api('/api/auth/logout','POST',{});signedIn(false);status('Signed out.');}catch(e){status(e.message);}};
function render(result){currentRef=result.reference;const panel=$('result');panel.replaceChildren(node('p','02 / ASSESSMENT','eyebrow'),node('div',result.risk_band.replaceAll('_',' '),'pill'));
  const risk=node('div',`${(result.bad_probability*100).toFixed(1)}%`,'risk');risk.append(node('small',' estimated bad-loan risk'));panel.append(risk,node('h3','Human review required'),node('p',result.recommendation,'muted'),node('h3','Reference comparisons'));
  const factors=node('ul');for(const factor of result.factors)factors.append(node('li',`${factor.feature}: ${(factor.probability_difference*100).toFixed(1)} percentage-point change versus the training median.`));panel.append(factors,node('p','One feature is replaced at a time. These comparisons are not causal and are not formal adverse-action reasons.','muted'));
  const warnings=node('ul');for(const warning of result.warnings)warnings.append(node('li',warning));panel.append(warnings);
  const button=node('button','Request optional AI explanation','ghost');button.onclick=async()=>{try{const res=await api(`/api/predictions/${currentRef}/explain`,'POST',{consent:true});panel.append(node('p',res.explanation,'muted'));}catch(e){status(e.message);}};
  const consent=node('p','Clicking sends only a coarse risk band and feature names to Hugging Face. The optional service must be configured by the operator.','muted');panel.append(button,consent);
}
$('application').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{const input=Object.fromEntries(new FormData(e.target));for(const [name,title,type] of fields)input[name]=Array.isArray(type)?(name==='payment_ach'||name==='bank_account_direct_deposit'?input[name]==='true':input[name]):Number(input[name]);render(await api('/api/predict','POST',input));status('Assessment saved to your account.');}catch(error){status(error.message);}finally{button.disabled=false;}};
$('batch-submit').onclick=async()=>{try{const input=JSON.parse($('batch-input').value);$('batch-result').textContent=JSON.stringify(await api('/api/predict/batch','POST',{applications:input}),null,2);status('Batch assessments saved.');}catch(e){status(e.message);}};
async function findings(){try{const m=await api('/api/model');$('auc').textContent=m.test.roc_auc.toFixed(3);$('recall').textContent=(m.test.recall_bad*100).toFixed(0)+'%';}catch(e){status(e.message);}}
async function refresh(){try{const [monitor,history]=await Promise.all([api('/api/monitoring'),api('/api/predictions')]);$('monitor-data').textContent=JSON.stringify(monitor,null,2);$('history').replaceChildren();for(const row of history){const tr=node('tr');for(const value of [new Date(row.created*1000).toLocaleDateString(),(row.bad_probability*100).toFixed(1)+'%',row.risk_band,row.outcome||'Pending'])tr.append(node('td',value));const actions=node('td');for(const label of ['Good','Bad','Delete']){const b=node('button',label,'ghost');b.onclick=async()=>{try{if(label==='Delete')await api('/api/predictions/'+row.reference,'DELETE');else await api(`/api/predictions/${row.reference}/outcome`,'POST',{outcome:label});refresh();}catch(e){status(e.message);}};actions.append(b);}tr.append(actions);$('history').append(tr);}if(!history.length){const tr=node('tr');const td=node('td','No assessments yet. Start with an application.');td.colSpan=5;tr.append(td);$('history').append(tr);}}catch(e){status(e.message);}}
$('refresh').onclick=refresh;
$('delete-account').onsubmit=async e=>{e.preventDefault();try{await api('/api/account','DELETE',{password:e.target.elements.password.value});e.target.reset();signedIn(false);status('Account and live assessment data deleted.');}catch(error){status(error.message);}};
(async()=>{try{const result=await api('/api/auth/me');csrf=result.csrf_token;signedIn(true);await findings();}catch{signedIn(false);}})();
