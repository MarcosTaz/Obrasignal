import { storage } from './storage';
import { authSession } from './authSession';

const API_BASE = (process.env.EXPO_PUBLIC_API_URL || 'https://obrasignal.onrender.com/api/v1').replace(/\/$/, '');
const DEFAULT_TIMEOUT = 20000;
const PROFILE_TIMEOUT = 20000;
const BACKEND_READY_TIMEOUT = 75000;
const SIGNOUT_WRITE_TIMEOUT = 5000;
const MAX_ATTEMPTS = 1;

let backendReadyPromise = null;

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function reportTiming(path, startedAt, status) {
  const durationMs = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt);
  if (typeof console !== 'undefined' && console.info) console.info('[ObraSignal startup]', { path, durationMs, status });
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') window.dispatchEvent(new CustomEvent('obrasignal:api-timing', { detail: { path, durationMs, status } }));
}
function isRetryableNetworkError(error) { if (!error) return false; if (error.name === 'AbortError') return true; if (typeof error.status === 'number') return [502,503,504].includes(error.status); return !error.status; }
function describeNetworkError(error, path) { const name=error?.name||'NetworkError'; const message=error?.message||String(error||'unknown error'); const hint=/load failed|failed to fetch|networkerror/i.test(message)?'O navegador não recebeu uma resposta HTTP. Verifica CORS, TLS, DNS ou se o endpoint está acessível.':message; const diagnostic=new Error(`API ${path}: ${hint} [${name}]`); diagnostic.code='API_NETWORK_ERROR'; diagnostic.causeMessage=message; diagnostic.path=path; diagnostic.apiBase=API_BASE; return diagnostic; }

async function request(path, options={}) {
  const timeout=options.timeout??DEFAULT_TIMEOUT;
  const maxAttempts=options.maxAttempts??MAX_ATTEMPTS;
  const skipAuth=options.skipAuth===true;
  const fetchOptions={...options};
  delete fetchOptions.timeout; delete fetchOptions.maxAttempts; delete fetchOptions.skipAuth;
  let lastError=null;
  let authRefreshes=0;
  const startedAt=typeof performance !== 'undefined'?performance.now():Date.now();
  for(let attempt=1;attempt<=maxAttempts;attempt+=1){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeout);
    try{
      const method=String(fetchOptions.method||'GET').toUpperCase();
      const authHeaders=skipAuth?{}:await authSession.authorizationHeader();
      const hasBody=fetchOptions.body!=null;
      const contentHeaders=hasBody||!['GET','HEAD'].includes(method)?{'Content-Type':'application/json'}:{};
      const response=await fetch(`${API_BASE}${path}`,{...fetchOptions,mode:'cors',cache:'no-store',headers:{Accept:'application/json',...contentHeaders,...(fetchOptions.headers||{}),...authHeaders},signal:controller.signal});
      const text=await response.text();
      let data=null; try{data=text?JSON.parse(text):null;}catch(_){}
      if(!response.ok){
        if(response.status===401 && !skipAuth && authRefreshes===0){
          authRefreshes+=1;
          let refreshedToken=null;
          try{refreshedToken=await authSession.refresh();}catch(_){}
          if(refreshedToken){ attempt-=1; continue; }
        }
        const error=new Error(data?.error||`HTTP ${response.status}`);error.status=response.status;error.responseBody=data;throw error;
      }
      reportTiming(path,startedAt,response.status);
      return data;
    }catch(error){
      lastError=isRetryableNetworkError(error)?describeNetworkError(error,path):error;
      if(!isRetryableNetworkError(error)||attempt>=maxAttempts){
        reportTiming(path,startedAt,error?.name==='AbortError'?'timeout':(error?.status||'network-error'));
        if(error?.name==='AbortError')throw new Error(`API ${path}: o servidor demorou demasiado tempo a responder. O Render pode estar a acordar.`);
        throw lastError;
      }
      await sleep(1500*attempt);
    }finally{clearTimeout(timer);}
  }
  throw lastError||new Error(`API ${path}: não foi possível concluir o pedido.`);
}

export function ensureBackendReady(){
  if(backendReadyPromise)return backendReadyPromise;
  const warmup=request('/health',{timeout:BACKEND_READY_TIMEOUT,skipAuth:true})
    .then(data=>{if(data?.ok!==true)throw new Error('API /health: resposta inválida.');return true})
    .finally(()=>{if(backendReadyPromise===warmup)backendReadyPromise=null});
  backendReadyPromise=warmup;
  return warmup;
}

async function readWhenReady(path,options={}){
  try{return await request(path,{...options,maxAttempts:1})}
  catch(error){
    if(!isRetryableNetworkError(error)&&error?.code!=='API_NETWORK_ERROR')throw error;
    await ensureBackendReady();
    return request(path,{...options,maxAttempts:1});
  }
}

async function writeWhenReady(path,options={}){
  await ensureBackendReady();
  return request(path,{...options,maxAttempts:1});
}

function normalizeOpportunity(item){if(!item||typeof item!=='object')return item;return {...item,decision_score:item.decision_score??item.account_score??null,decision_reason:item.decision_reason??item.account_reason??null};}
function unwrapProfile(data){
  if(data===null||data===undefined)return null;
  if(typeof data!=='object'||Array.isArray(data)||!Object.prototype.hasOwnProperty.call(data,'profile'))throw new Error('API /profile: contrato de resposta inválido.');
  const profile=data.profile;
  if(profile===null)return null;
  if(typeof profile!=='object'||Array.isArray(profile))throw new Error('API /profile: perfil inválido.');
  return profile;
}

export const api={
  health:()=>ensureBackendReady(),
  profile:async()=>unwrapProfile(await readWhenReady('/profile',{timeout:PROFILE_TIMEOUT})),
  saveProfile:async(profile)=>unwrapProfile(await writeWhenReady('/profile',{method:'POST',body:JSON.stringify(profile||{}),timeout:PROFILE_TIMEOUT})),
  billingStatus:()=>readWhenReady('/billing/status'),
  accountExport:()=>readWhenReady('/account/export'),
  accountDeletionStatus:()=>readWhenReady('/account/deletion'),
  requestAccountDeletion:(confirmation)=>writeWhenReady('/account/deletion',{method:'POST',body:JSON.stringify({confirmation})}),
  stats:()=>readWhenReady('/stats'),
  sourceHealth:({source=''}={})=>{const p=new URLSearchParams();if(source)p.set('source',source);const query=p.toString();return readWhenReady(`/source-health-contract${query?`?${query}`:''}`);},
  workflowStats:()=>readWhenReady('/workflow/stats'),
  alerts:({limit=20,unreadOnly=false}={})=>{const p=new URLSearchParams({limit:String(limit)});if(unreadOnly)p.set('unread','1');return readWhenReady(`/alerts?${p.toString()}`);},
  markAlertDelivered:(eventId)=>writeWhenReady(`/alerts/${encodeURIComponent(eventId)}/delivered`,{method:'POST',body:JSON.stringify({})}),
  registerPushDevice:({installationId,expoPushToken,platform})=>writeWhenReady('/push/devices',{method:'POST',body:JSON.stringify({installation_id:installationId,expo_push_token:expoPushToken,platform})}),
  unregisterPushDevice:(installationId)=>request('/push/devices',{method:'DELETE',body:JSON.stringify({installation_id:installationId}),timeout:SIGNOUT_WRITE_TIMEOUT,maxAttempts:1}),
  opportunities:async({q='',minscore=0,source='',limit=60,offset=0,openOnly=false}={})=>{const p=new URLSearchParams({limit:String(limit),offset:String(offset),minscore:String(minscore)});if(q.trim())p.set('q',q.trim());if(source)p.set('source',source);if(openOnly)p.set('open','1');const data=await readWhenReady(`/opportunities?${p.toString()}`);return data?{...data,items:(data.items||[]).map(normalizeOpportunity)}:data;},
  opportunity:async(id)=>normalizeOpportunity(await readWhenReady(`/opportunities/${encodeURIComponent(id)}`)),
  workflow:(id)=>readWhenReady(`/opportunities/${encodeURIComponent(id)}/workflow`),
  setWorkflow:(id,status,note)=>writeWhenReady(`/opportunities/${encodeURIComponent(id)}/workflow`,{method:'POST',body:JSON.stringify({status,note:note||null})}),
  saveOpportunity:(id)=>writeWhenReady(`/opportunities/${encodeURIComponent(id)}/save`,{method:'POST',body:JSON.stringify({})}),
  unsaveOpportunity:(id)=>writeWhenReady(`/opportunities/${encodeURIComponent(id)}/save`,{method:'DELETE'}),
  savedOpportunity:(id)=>readWhenReady(`/opportunities/${encodeURIComponent(id)}/watch`),
  updateSavedOpportunity:(id,patch)=>writeWhenReady(`/opportunities/${encodeURIComponent(id)}/watch`,{method:'PATCH',body:JSON.stringify(patch||{})}),
  savedOpportunities:({status='',priority='',order='recent',limit=20,offset=0}={})=>{const p=new URLSearchParams({order:String(order),limit:String(limit),offset:String(offset)});if(status)p.set('status',status);if(priority)p.set('priority',priority);return readWhenReady(`/opportunities/saved?${p.toString()}`);}
};
export { API_BASE };
