import test from 'node:test';
import assert from 'node:assert/strict';
import {composeInvitedDisplayName,neonInviteSignUp} from './neon-invite-client.mjs';
const code='OS-'+'a'.repeat(48);
test('invite code is attached to signup name and remains out of log output',()=>{
  assert.equal(composeInvitedDisplayName(code,'  Empresa  '),code+'|Empresa');
  for(const candidate of ['invalid','OS-'+ 'X'.repeat(48),'OS-'+'a'.repeat(47)])
    assert.throws(()=>composeInvitedDisplayName(candidate,'Empresa'),/invalid_invitation/);
});
test('provider receives normalized email and bound invite but never cross-origin',async()=>{
  let sent;
  const fetcher=async(url,opts)=>{sent={url,opts};return {ok:true,status:200}};
  const result=await neonInviteSignUp({email:'  CONTACT@EXAMPLE.COM ',password:'strong-password123',code,displayName:'Empresa'}, {fetcher});
  assert.deepEqual(result,{ok:true,status:200});
  assert.equal(new URL(sent.url).pathname.endsWith('/auth/sign-up/email'),true);
  assert.equal(JSON.parse(sent.opts.body).email,'contact@example.com');
  assert.equal(JSON.parse(sent.opts.body).name,code+'|Empresa');
  assert.throws(()=>composeInvitedDisplayName(code,'Bad|Injected'),/invalid_display_name/);
  await assert.rejects(()=>neonInviteSignUp({email:'a@example.com',password:'strong-password123',code,displayName:'X'},{fetcher,baseUrl:'https://evil.example/auth'}),/auth_endpoint_not_trusted/);
});
test('signup failures never expose provider response or invitation',async()=>{
  const fetcher=async()=>({ok:false,status:403,json:async()=>({token:code})});
  const result=await neonInviteSignUp({email:'test@example.com',password:'strong-password123',code,displayName:'Sample'},{fetcher});
  assert.deepEqual(result,{ok:false,status:403,reason:'invitation_or_signup_rejected'});
  assert.ok(!JSON.stringify(result).includes(code));
});
test('missing or invalid credentials do not reach provider',async()=>{
  let count=0;const fetcher=()=>{count++;throw Error('must not call')};
  for(const value of [{email:'bad',password:'strong-password123',code,displayName:'Valid'},{email:'a@example.com',password:'short',code,displayName:'Valid'}])
    await assert.rejects(()=>neonInviteSignUp(value,{fetcher}));
  assert.equal(count,0);
});
