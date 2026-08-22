import { supabase } from '../lib/supabase';
import { storage } from './storage';

const API_BASE = (process.env.EXPO_PUBLIC_API_URL || 'https://obrasignal.onrender.com/api/v1').replace(/\/$/, '');
const DEFAULT_TIMEOUT = 20000;
const PROFILE_TIMEOUT = 20000;
const MAX_ATTEMPTS = 1;

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
      let {data:{session}}=skipAuth?{data:{session:null}}:await supabase.auth.getSession();
      const authHeaders=session?.access_token?{Authorization:`Bearer ${session.access_token}`}:{ };
      const method=String(fetchOptions.method||'GET').toUpperCase();
      const hasBody=fetchOptions.body!=null;
      const contentHeaders=hasBody||!['GET','HEAD'].includes(method)?{'Content-Type':'application/json'}:{};
      const response=await fetch(`${API_BASE}${path}`,{...fetchOptions,mode:'cors',cache:'no-store',headers:{Accept:'application/json',...contentHeaders,...authHeaders,...(fetchOptions.headers||{})},signal:controller.signal});
      const text=await response.text();
      let data=null; try{data=text?JSON.parse(text):null;}catch(_){}
      if(!response.ok){
        if(response.status===401 && !skipAuth && authRefreshes===0){
          authRefreshes+=1;
          const refreshed=await supabase.auth.refreshSession();
          session=refreshed?.data?.session || null;
          if(session?.access_token){ continue; }
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

function normalizeOpportunity(item){if(!item||typeof item!=='object')return item;return {...item,decision_score:item.decision_score??item.account_score??null,decision_reason:item.decision_reason??item.account_reason??null};}
function unwrapProfile(data){return data?.profile||data||null;}

export const api={
  health:()=>request('/health',{timeout:60000,skipAuth:true}),
  profile:async()=>{try{return unwrapProfile(await request('/profile',{timeout:PROFILE_TIMEOUT}));}catch(error){const local=await storage.getProfile().catch(()=>null);if(local)return local;throw error;}},
  // POST is intentionally single-attempt: retrying an authenticated write can
  // duplicate work and makes a stuck Save button look like a UI failure.
  saveProfile:async(profile)=>unwrapProfile(await request('/profile',{method:'POST',body:JSON.stringify(profile||{}),timeout:PROFILE_TIMEOUT,maxAttempts:1})),
  billingStatus:()=>request('/billing/status'),
  stats:()=>request('/stats'),
  workflowStats:()=>request('/workflow/stats'),
  alerts:({limit=20,unreadOnly=false}={})=>{const p=new URLSearchParams({limit:String(limit)});if(unreadOnly)p.set('unread','1');return request(`/alerts?${p.toString()}`);},
  markAlertDelivered:(eventId)=>request(`/alerts/${encodeURIComponent(eventId)}/delivered`,{method:'POST',body:JSON.stringify({})}),
  opportunities:async({q='',minscore=0,source='',limit=60,openOnly=false}={})=>{const p=new URLSearchParams({limit:String(limit),minscore:String(minscore)});if(q.trim())p.set('q',q.trim());if(source)p.set('source',source);if(openOnly)p.set('open','1');const data=await request(`/opportunities?${p.toString()}`);return data?{...data,items:(data.items||[]).map(normalizeOpportunity)}:data;},
  opportunity:async(id)=>normalizeOpportunity(await request(`/opportunities/${encodeURIComponent(id)}`)),
  workflow:(id)=>request(`/opportunities/${encodeURIComponent(id)}/workflow`),
  setWorkflow:(id,status,note)=>request(`/opportunities/${encodeURIComponent(id)}/workflow`,{method:'POST',body:JSON.stringify({status,note:note||null})})
};
export { API_BASE };
