// Restricted ObraSignal Neon Auth invitation client. Not a Supabase session adapter.
export const OBRA_NEON_AUTH_URL = 'https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth';
const INVITE=/^OS-[0-9a-f]{48}$/;
const EMAIL=/^[^\s@]{1,64}@[^\s@]{1,189}$/;

function normalizeEmail(email) {
  const normalized = String(email ?? '').trim().toLowerCase();
  if (normalized.length > 254 || !EMAIL.test(normalized)) throw new Error('invalid_email');
  return normalized;
}
export function composeInvitedDisplayName(code, displayName) {
  if (typeof code !== 'string' || !INVITE.test(code)) throw new Error('invalid_invitation');
  const name = String(displayName ?? '').trim();
  if (!name || name.length > 160 || name.includes('|')) throw new Error('invalid_display_name');
  return code + '|' + name;
}
export async function neonInviteSignUp({email, password, code, displayName}, {fetcher=fetch, baseUrl=OBRA_NEON_AUTH_URL}={}) {
  const normalized = normalizeEmail(email);
  if (typeof password!=='string' || password.length<8 || password.length>128) throw new Error('invalid_password');
  const name=composeInvitedDisplayName(code,displayName);
  const expected=new URL(OBRA_NEON_AUTH_URL);
  const actual=new URL(baseUrl);
  if (actual.protocol!=='https:' || actual.origin!==expected.origin || actual.pathname!==expected.pathname) throw new Error('auth_endpoint_not_trusted');
  const response=await fetcher(actual.href.replace(/\/$/,'')+'/sign-up/email',{
    method:'POST',
    headers:{'Content-Type':'application/json','Accept':'application/json'},
    credentials:'include',
    body:JSON.stringify({email:normalized,password,name}),
  });
  if (!response.ok) {
    // Do not forward provider response bodies: may leak credential or invitation values.
    return {ok:false,status:response.status,reason:response.status===429?'rate_limited':response.status>=500?'provider_unavailable':'invitation_or_signup_rejected'};
  }
  return {ok:true,status:response.status};
}
