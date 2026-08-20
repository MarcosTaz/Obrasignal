import { supabase } from '../lib/supabase';

const API_BASE = (process.env.EXPO_PUBLIC_API_URL || 'https://obrasignal.onrender.com/api/v1').replace(/\/$/, '');
const DEFAULT_TIMEOUT = 120000;
const PROFILE_TIMEOUT = 150000;
const MAX_ATTEMPTS = 2;
let readinessPromise = null;

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function isRetryableNetworkError(error) { if (!error) return false; if (error.name === 'AbortError') return true; if (typeof error.status === 'number') return [502,503,504].includes(error.status); return !error.status; }
function describeNetworkError(error, path) { const name=error?.name||'NetworkError'; const message=error?.message||String(error||'unknown error'); const hint=/load failed|failed to fetch|networkerror/i.test(message)?'O navegador não recebeu uma resposta HTTP. Verifica CORS, TLS, DNS ou se o endpoint está acessível.':message; const diagnostic=new Error(`API ${path}: ${hint} [${name}]`); diagnostic.code='API_NETWORK_ERROR'; diagnostic.causeMessage=message; diagnostic.path=path; diagnostic.apiBase=API_BASE; return diagnostic; }

async function ensureReady() {
  if (!readinessPromise) {
    readinessPromise = request('/health', { timeout: 90000, maxAttempts: 1, skipAuth: true })
      .catch((error) => { readinessPromise = null; throw error; });
  }
  return readinessPromise;
}

async function request(path, options={}) {
  const timeout=options.timeout??DEFAULT_TIMEOUT;
  const maxAttempts=options.maxAttempts??MAX_ATTEMPTS;
  const skipAuth=options.skipAuth===true;
  const fetchOptions={...options};
  delete fetchOptions.timeout; delete fetchOptions.maxAttempts; delete fetchOptions.skipAuth;
  let lastError=null;
  let authRefreshes=0;
  for(let attempt=1;attempt<=maxAttempts;attempt+=1){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeout);
    try{
      // Do not race authenticated calls against a sleeping Render instance.
      // Health is public and is deliberately requested before the first protected call.
      if (!skipAuth && path !== '/health') await ensureReady();
      let {data:{session}}=skipAuth?{data:{session:null}}:await supabase.auth.getSession();
      const authHeaders=session?.access_token?{Authorization:`Bearer ${session.access_token}`}:{ };
      const method=String(fetchOptions.method||'GET').toUpperCase();
      const hasBody=fetchOptions.body!=null;
      const contentHeaders=hasBody||!['GET','HEAD'].includes(method)?{'Content-Type':'application/json'}:{};
      const response=await fetch(`${API_BASE}${path}`,{...fetchOptions,mode:'cors',cache:'no-store',headers:{Accept:'application/json',...contentHeaders,...authHeaders,...(fetchOptions.headers||{})},signal:controller.signal});
      const text=await response.text();
      let data=null; try{data=text?JSON.parse(text):null;}catch(_){}
      if(!response.ok){
        // A browser can hold an expired Supabase access token even though the
        // local session still exists. Refresh it once before surfacing 401.
        if(response.status===401 && !skipAuth && authRefreshes===0){
          authRefreshes+=1;
          const refreshed=await supabase.auth.refreshSession();
          session=refreshed?.data?.session || null;
          if(session?.access_token){ continue; }
        }
        const error=new Error(data?.error||`HTTP ${response.status}`);error.status=response.status;error.responseBody=data;throw error;
      }
      return data;
    }catch(error){
      lastError=isRetryableNetworkError(error)?describeNetworkError(error,path):error;
      if(!isRetryableNetworkError(error)||attempt>=maxAttempts){
        if(error?.name==='AbortError')throw new Error(`API ${path}: o servidor demorou demasiado tempo a responder. O Render pode estar a acordar.`);
        throw lastError;
      }
      await sleep(1500*attempt);
    }finally{clearTimeout(timer);}
  }
  throw lastError||new Error(`API ${path}: não foi possível concluir o pedido.`);
}

function normalizeOpportunity(item){if(!item||typeof item!=='object')return item;return {...item,decision_score:item.decision_score??item.account_score??null,decision_reason:item.decision_reason??item.account_reason??null};}

export const api={
  warmup:()=>{ readinessPromise=null; return ensureReady(); },
  health:()=>request('/health',{timeout:90000,skipAuth:true}),
  profile:()=>request('/profile',{timeout:PROFILE_TIMEOUT}),
  saveProfile:(profile)=>request('/profile',{method:'POST',body:JSON.stringify(profile||{}),timeout:PROFILE_TIMEOUT}),
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