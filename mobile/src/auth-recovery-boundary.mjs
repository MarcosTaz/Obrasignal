/**
 * Password recovery is a temporary identity capability, never a normal tenant
 * session. An OAuth/PKCE return MUST NOT grant workspace access by itself.
 */
export function isRecoveryReturn(url) {
  try {
    const parsed=new URL(url);
    return parsed.searchParams.get('type')==='recovery' ||
      new URLSearchParams(parsed.hash.slice(1)).get('type')==='recovery';
  } catch (_) {return false}
}
export function nextRecoveryScope({signedIn,recovery,tenantId}) {
  if(!signedIn)return {bind:null,openWorkspace:false,mode:recovery?'invalid-link':'signed-out'};
  if(recovery)return {bind:null,openWorkspace:false,mode:'reset-only'};
  if(!tenantId)return {bind:null,openWorkspace:false,mode:'invalid-session'};
  return {bind:tenantId,openWorkspace:true,mode:'customer'};
}
