const configuredBase=process.env.EXPO_PUBLIC_API_URL||'https://obrasignal.onrender.com/api/v1';
const API_BASE=configuredBase.endsWith('/')?configuredBase.slice(0,-1):configuredBase;
export function classifyAuthHealth(payload){
  if(!payload || payload.ok!==true)return {state:'unknown',message:''};
  const auth=payload.auth||{};
  if(auth.mode!=='provider'||auth.config_present!==true)return {state:'degraded',message:'Sign-in and password recovery are temporarily unavailable. Account identities remain protected.'};
  if(auth.provider_status==='ready' && payload.runtime?.auth_warm_status==='ready')return {state:'ready',message:''};
  if(auth.provider_status==='degraded'||auth.provider_error)return {state:'degraded',message:'The identity provider is currently unreachable. Password reset requests may fail; no recovery email is confirmed.'};
  return {state:'unknown',message:''};
}
export async function readAuthHealth({signal}={}){
  try{
    const response=await fetch(API_BASE+'/health',{method:'GET',cache:'no-store',headers:{Accept:'application/json'},signal});
    if(!response.ok)return {state:'unknown',message:''};
    return classifyAuthHealth(await response.json());
  }catch(_){return {state:'unknown',message:''}}
}
