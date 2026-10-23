import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {classifyAuthFailure} from './auth-failure-feedback.mjs';

test('a DNS/network outage is not misreported as incorrect credentials',()=>{
  for(const error of [
    new TypeError('Failed to fetch'),
    {message:'Network request failed',name:'AuthRetryableFetchError',status:0},
    {message:'fetch failed',cause:{code:'ENOTFOUND'}},
    {message:'The operation timed out',status:0},
  ]) {
    const out=classifyAuthFailure(error,'login');
    assert.equal(out.category,'network_unavailable');
    assert.equal(out.retryable,true);
    assert.match(out.message,/serviço de autenticação/);
    assert.doesNotMatch(out.message,/senha incorreta|palavra-passe incorreta/i);
  }
});
test('actual invalid credentials is classified separately from provider failures',()=>{
  assert.equal(classifyAuthFailure({code:'invalid_credentials',status:400},'login').category,'invalid_credentials');
  assert.equal(classifyAuthFailure({message:'Invalid login credentials',status:400},'login').category,'invalid_credentials');
  assert.equal(classifyAuthFailure({code:'email_not_confirmed',status:400},'login').category,'email_unconfirmed');
});
test('rate limit and recovery errors do not fabricate a sent email',()=>{
  assert.equal(classifyAuthFailure({code:'over_email_send_rate_limit',status:429},'recovery').category,'rate_limited');
  assert.equal(classifyAuthFailure({status:500,message:'Internal Server Error'},'recovery').category,'unavailable');
  assert.match(classifyAuthFailure({status:500},'recovery').message,/Nenhum envio está confirmado/);
});
test('upstream exception content never leaks to account UI',()=>{
  for(const action of ['login','recovery']){
    const out=classifyAuthFailure({
      message:'secret=topsecret bearer eyJhbGciOiJIUzI1NiJ9 https://old-provider.invalid/auth/v1/token',
      status:500,
      code:'bad_request'
    },action);
    assert.doesNotMatch(out.message,/topsecret|eyJhb|invalid\/auth|bad_request|old-provider/);
  }
});
test('a public client cannot call signUp while provider security boundary is unproven',()=>{
  const auth=readFileSync(new URL('../components/AuthScreen.tsx',import.meta.url),'utf8');
  assert.doesNotMatch(auth,/supabase\.auth\.signUp|Criar conta|onSignup/);
  assert.match(auth,/signInWithPassword/);
  assert.match(auth,/classifyAuthFailure\(e, 'login'\)/);
  assert.match(auth,/classifyAuthFailure\(e, 'recovery'\)/);
  assert.match(auth,/Pedir convite/);
});
