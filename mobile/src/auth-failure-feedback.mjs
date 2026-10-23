const NETWORK=/failed to fetch|fetch failed|network request failed|networkerror|load failed|dns|enotfound|econnreset|timeout|timed out/i;
export function classifyAuthFailure(e,action='login'){
 const code=String(e?.code||'').toLowerCase();
 const status=Number(e?.status||0);
 const details=String(e?.message||'');
 if(NETWORK.test(details)||e?.name==='AuthRetryableFetchError')return {kind:'network',message:'Authentication is temporarily unavailable. We could not contact the identity provider. This does not mean your password is incorrect.'};
 if(status===429||/rate_limit|too_many_requests/.test(code))return {kind:'limit',message:'Too many requests. Please wait before trying again.'};
 if(action==='login'&&(code==='invalid_credentials'||/invalid login credentials/i.test(details)))return {kind:'invalid',message:'Email or password was not recognised. Check your credentials.'};
 return {kind:'unavailable',message:action==='recovery'?'The identity provider did not confirm a reset request. No recovery email has been confirmed. Try again later.':'Sign-in could not be completed. Please try again later.'};
}
