// Isolated Neon Better Auth cookie-session bridge for preview/staging.
// A Better Auth session cookie is NOT a JWT and must not be sent to the
// ObraSignal API as Authorization: Bearer. Full migration is intentionally gated.
export const NEON_AUTH_BASE = 'https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth';

export function makeNeonSessionAdapter({fetcher = fetch, baseUrl = NEON_AUTH_BASE} = {}) {
  if (baseUrl !== NEON_AUTH_BASE) throw new Error('untrusted_neon_auth_endpoint');
  async function call(path, body) {
    const response = await fetcher(baseUrl + path, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'include',
      headers: {'Accept':'application/json', ...(body === undefined ? {} : {'Content-Type':'application/json'})},
      ...(body === undefined ? {} : {body:JSON.stringify(body)}),
    });
    if (!response.ok) return {ok:false,status:response.status};
    const data = await response.json().catch(() => null);
    return {ok:true,status:response.status,data};
  }
  return {
    async signIn(email, password) {
      if(typeof email !== 'string' || !email.trim().includes('@') ||
         typeof password !== 'string' || !password) throw new Error('invalid_credentials');
      const response = await call('/sign-in/email',{email:email.trim().toLowerCase(),password});
      if(!response.ok) return {ok:false,status:response.status};
      return {ok:true};
    },
    async getSession() {
      const result = await call('/get-session');
      if(!result.ok) return {authenticated:false};
      const user = result.data?.user;
      if(!user?.id || !user?.email) return {authenticated:false};
      return {authenticated:true,user:{id:user.id,email:user.email}};
    },
    async signOut() {
      const result = await call('/sign-out',{});
      return {ok:result.ok};
    },
    async authorizationHeader() {
      // Deliberate deny-by-default: Neon cookie sessions cannot impersonate a
      // validated JWT. Enable only after live token exchange + backend tests.
      throw new Error('neon_bearer_exchange_not_yet_verified');
    },
  };
}
