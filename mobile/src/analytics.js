const API_BASE = (process.env.EXPO_PUBLIC_API_URL || '').replace(/\/$/, '');
const BUILD_ID = process.env.EXPO_PUBLIC_BUILD_ID || '';
const ALLOWED_EVENTS = new Set(['page_view','authenticated_session','profile_completed','opportunity_opened','checkout_opened','checkout_completed']);

function browserContext(){
  if(typeof window==='undefined'||typeof document==='undefined') return null;
  const params=new URLSearchParams(window.location.search||'');
  const width=window.innerWidth||0;
  return {
    path:window.location.pathname||'/',
    referrer:document.referrer||'',
    utm_source:params.get('utm_source')||'',
    utm_medium:params.get('utm_medium')||'',
    utm_campaign:params.get('utm_campaign')||'',
    timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'',
    language:navigator.language||'',
    device:width<760?'mobile':width<1100?'tablet':'desktop',
    build_id:BUILD_ID,
  };
}

export function trackTraffic(event, extra={}){
  if(!ALLOWED_EVENTS.has(event)||!API_BASE||typeof fetch==='undefined') return Promise.resolve(false);
  const base=browserContext();
  if(!base) return Promise.resolve(false);
  const payload={...base,...extra,event};
  return fetch(`${API_BASE}/analytics/event`,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload),
    keepalive:true,
    credentials:'omit',
  }).then(response=>response.ok).catch(()=>false);
}
