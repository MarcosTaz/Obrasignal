import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {classifyAuthFailure} from './auth-failure-feedback.mjs';
import {getContact,contactLink,PUBLIC_CONTACTS} from './public-contacts.mjs';
const source=(p)=>readFileSync(new URL(p,import.meta.url),'utf8');

test('radar visibly scans, finds a distinct map pin, then fades into a large official logo',()=>{
 const c=source('../components/WebIntro.js');
 for(const part of ['rotate:sweep','targetOpacity','targetScale','brandOpacity','brandScale','SCANNING PUBLIC PROCUREMENT SIGNALS','SIGNAL FOUND','<BrandLogo','markSize={small?105:150}','Skip introduction','isReduceMotionEnabled']){
  assert.ok(c.includes(part),part);
 }
 assert.match(c,/fill=\{COLORS\.copper\}/);
 assert.match(c,/SCANNING PUBLIC PROCUREMENT SIGNALS/);
 assert.doesNotMatch(c,/backgroundColor:BRAND\.paper/);
});
test('privacy, support, and legal contacts are never invented or hard coded',()=>{
 const auth=source('../components/AuthScreen.tsx');
 const legal=source('../components/AuthGate.js');
 assert.doesNotMatch(auth+legal,/obrasignal\.pt@gmail\.com/i);
 assert.match(legal,/getContact\('privacy'\)/);
 assert.match(legal,/getContact\('legal'\)/);
 assert.match(legal,/CONTACT_UNVERIFIED_MESSAGE/);
 assert.equal(getContact('imaginary-role'),null);
 if(!process.env.EXPO_PUBLIC_OBRASIGNAL_SUPPORT_EMAIL)assert.equal(contactLink('support'),null);
 assert.equal(Object.keys(PUBLIC_CONTACTS).length,3);
});
test('password recovery has a distinct flow and does not claim delivery on failure',()=>{
 const auth=source('../components/AuthScreen.tsx');
 const recovery=source('../components/PasswordRecovery.js');
 assert.match(auth,/recoveryMode\?reset:submit/);
 assert.match(auth,/resetPasswordForEmail/);
 assert.match(auth,/\?type=recovery/);
 assert.match(auth,/classifyAuthFailure\(e,'recovery'\)/);
 assert.match(auth,/Send recovery link/);
 assert.match(recovery,/updateUser\(\{password\}\)/);
 assert.match(recovery,/await supabase\.auth\.signOut\(\)/);
});
test('network failures are distinguished from incorrect passwords',()=>{
 assert.equal(classifyAuthFailure(new TypeError('Failed to fetch')).kind,'network');
 assert.equal(classifyAuthFailure({code:'invalid_credentials',status:400}).kind,'invalid');
 const e=classifyAuthFailure({message:'token secret as https://private.example'},'recovery');
 assert.doesNotMatch(e.message,/secret|private\.example/);
});
test('night palette and institutional typography span marketing, login, workspace and session chrome',()=>{
 for(const p of ['../components/WebIntro.js','../components/WorldExperience.js','../components/AuthScreen.tsx','../App.web.js','../components/AuthGate.js','../components/PasswordRecovery.js']){
  assert.match(source(p),/typography\.mjs/,'missing typography '+p);
 }
 assert.match(source('../index.js'),/backgroundColor: '#06111D'/);
 assert.match(source('../components/SecurityTrustBar.js'),/SECURITY & TRUST/);
});


test('cinematic sequence holds the official logo before dissolving the night overlay',async()=>{
 const intro=source('../components/WebIntro.js');
 const timings=await import('./intro-timeline.mjs');
 assert.match(intro,/Animated\.sequence\(\[/);
 assert.match(intro,/Animated\.delay\(INTRO_BRAND_HOLD_MS\)/);
 assert.match(intro,/opacity:exitOpacity/);
 assert.match(intro,/duration:INTRO_EXIT_MS/);
 assert.match(intro,/setReduceMotion\(Boolean\(v\)\)/);
 assert.match(intro,/if\(reduceMotion===null\)return undefined/);
 assert.match(intro,/onPress=\{finish\}/);
 assert.equal(timings.INTRO_TOTAL_MS,timings.INTRO_SCAN_MS+timings.INTRO_BRAND_HOLD_MS+timings.INTRO_EXIT_MS);
 assert.ok(timings.INTRO_BRAND_HOLD_MS>=700);
 assert.ok(timings.INTRO_EXIT_MS>=600);
 assert.ok(timings.INTRO_WATCHDOG_MS>timings.INTRO_TOTAL_MS);
});

test('acquisition marker appears when the rotating scan reaches its approximate bearing',async()=>{
 const t=await import('./intro-timeline.mjs');
 const bearing=t.sweepDegreesAt(t.INTRO_SIGNAL_PROGRESS);
 // Scan line in the SVG points approximately -58 degrees before rotation.
 const beamHeading=-58+bearing;
 // The abstract upper-right target is 19% to the right and 23% above centre.
 const targetHeading=Math.atan2(-23,19)*180/Math.PI;
 assert.ok(Math.abs(beamHeading-targetHeading)<9);
 assert.ok(t.INTRO_SIGNAL_PROGRESS>=.38 && t.INTRO_SIGNAL_PROGRESS<=.48);
 assert.equal(t.sweepDegreesAt(-2),t.INTRO_SWEEP_START_DEG);
 assert.equal(t.sweepDegreesAt(2),t.INTRO_SWEEP_END_DEG);
});
