import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isRecoveryReturn,nextRecoveryScope} from './auth-recovery-boundary.mjs';
import {classifyAuthHealth} from './auth-provider-health.mjs';
const file=p=>readFileSync(new URL(p,import.meta.url),'utf8');
test('recovery link is detected in search and hash but not arbitrary URLs',()=>{
 assert.equal(isRecoveryReturn('https://obrasignal.com/?type=recovery#access_token=test'),true);
 assert.equal(isRecoveryReturn('https://obrasignal.com/#type=recovery&access_token=x'),true);
 assert.equal(isRecoveryReturn('https://obrasignal.com/?type=signup'),false);
 assert.equal(isRecoveryReturn('malformed'),false);
});
test('recovery JWT never binds account tenant or opens workspace',()=>{
 assert.deepEqual(nextRecoveryScope({signedIn:true,recovery:true,tenantId:'company-a'}),{bind:null,openWorkspace:false,mode:'reset-only'});
 assert.deepEqual(nextRecoveryScope({signedIn:false,recovery:true}),{bind:null,openWorkspace:false,mode:'invalid-link'});
 assert.deepEqual(nextRecoveryScope({signedIn:true,recovery:false,tenantId:'company-a'}),{bind:'company-a',openWorkspace:true,mode:'customer'});
});
test('provider DNS outage is displayed as service incident, not invalid password',()=>{
 const health=classifyAuthHealth({ok:true,auth:{mode:'provider',config_present:true,provider_status:'degraded',provider_error:'dns_error'},runtime:{auth_warm_status:'degraded'}});
 assert.equal(health.state,'degraded');
 assert.doesNotMatch(health.message,/password was wrong|invalid credentials/i);
 assert.equal(classifyAuthHealth({ok:true,auth:{mode:'provider',config_present:true,provider_status:'ready'},runtime:{auth_warm_status:'ready'}}).state,'ready');
});
test('source gates recovery UI before private workspace and never treats reset as login',()=>{
 const gate=file('../components/AuthGate.js');
 assert.ok(gate.indexOf('if (passwordRecovery)')<gate.indexOf('return <AccountPrivacyControls>'));
 assert.match(gate,/storage\.bindPrivateTenant\(null\)/);
 assert.match(gate,/recoveryRef\.current/);
 assert.match(gate,/if \(signedIn && recoveryRef\.current\)/);
 assert.match(gate,/if \(passwordRecovery && authState\.status !== 'signed-in'\)/);
});
test('password update and sign-out are distinct statuses',()=>{
 const source=file('../components/PasswordRecovery.js');
 assert.match(source,/setPasswordUpdated\(true\)/);
 assert.match(source,/Retry secure sign-out/);
 assert.match(source,/signOutError/);
 assert.match(source,/Password updated, but we could not end the recovery session/);
});
