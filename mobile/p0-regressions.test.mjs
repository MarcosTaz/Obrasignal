import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');

test('Profile tab renders its own loading/error state while Render is cold', () => {
  assert.match(app, /tab==='profile'\?<>{profile\?<Profile/);
  assert.match(app, /A carregar o perfil/);
  assert.match(app, /profileError\?<ErrorNotice/);
});

test('profile GET cannot disguise cache fallback as a fresh response', () => {
  assert.match(api, /profile:async\(\)=>unwrapProfile\(await readWhenReady\('\/profile'/);
  assert.doesNotMatch(api, /profile:async\(\)=>\{try[\s\S]*storage\.getProfile/);
});

test('a successful session refresh retries the original request once', () => {
  assert.match(api, /response\.status===401[\s\S]*supabase\.auth\.refreshSession\(\)/);
  assert.match(api, /session\?\.access_token\)\{ attempt-=1; continue; \}/);
});

test('startup hydrates cache first but refreshes using hydrated criteria', () => {
  assert.match(app, /Promise\.allSettled\(\[storage\.getSettings\(\),storage\.getCache\(\),storage\.getProfile\(\)\]\)/);
  assert.match(app, /load\(\{preserve:true,criteria:savedSettings\}\)/);
  assert.match(app, /minscore:criteria\.minScore/);
});

test('fresh Radar response replaces cache and failures remain visible and retryable', () => {
  assert.match(app, /const freshItems=opResult\.value\?\.items\|\|\[\];/);
  assert.match(app, /setItems\(freshItems\)/);
  assert.match(app, /setRadarError\(opResult\.reason/);
  assert.match(app, /radarError\?<ErrorNotice message=\{radarError\} onRetry=\{onRefresh\}/);
});

test('overlapping refreshes cannot let stale responses win and flags always terminate', () => {
  assert.match(app, /const id=\+\+requestId\.current/);
  assert.match(app, /id!==requestId\.current\)return/);
  assert.match(app, /finally\{if\(mounted\.current&&id===requestId\.current\)\{setDataLoading\(false\);setRefreshing\(false\);setProfileLoading\(false\)/);
});

test('saving Profile awaits a server-backed Radar refresh before completing', () => {
  assert.match(app, /api\.saveProfile[\s\S]*setTab\('radar'\);await load\(\{manual:true\}\)/);
});

test('changing Radar criteria immediately requests matching server data', () => {
  assert.match(app, /applyCriteria=patch=>\{const criteria=\{\.\.\.settings,\.\.\.patch\};setSettings\(criteria\);load\(\{manual:true,criteria\}\)\}/);
  assert.match(app, /applyMinScore=value=>applyCriteria\(\{minScore:value\}\)/);
  assert.match(app, /onPress=\{\(\)=>applyMinScore\(v\)\}/);
});

test('changing open-only immediately refreshes Radar from the server with the new criterion', () => {
  assert.match(app, /onOpenOnlyChange=\{value=>applyCriteria\(\{openOnly:value\}\)\}/);
  assert.match(app, /<Switch value=\{!!settings\.openOnly\} onValueChange=\{onOpenOnlyChange\}\/>/);
  assert.match(app, /api\.opportunities\(\{q:search,minscore:criteria\.minScore,openOnly:criteria\.openOnly/);
});


test('authenticated session starts one non-blocking backend warm-up', () => {
  const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
  assert.match(authGate, /setLoading\(false\)\n\s*if \(data\.session\) ensureBackendReady\(\)\.catch/);
  assert.match(api, /if\(backendReadyPromise\)return backendReadyPromise/);
  assert.match(api, /BACKEND_READY_TIMEOUT = 75000/);
});

test('warm backend keeps the GET fast and a cold GET is repeated only once after readiness', () => {
  assert.match(api, /try\{return await request\(path,\{\.\.\.options,maxAttempts:1\}\)\}[\s\S]*await ensureBackendReady\(\);\n\s*return request\(path,\{\.\.\.options,maxAttempts:1\}\)/);
  assert.match(api, /const MAX_ATTEMPTS = 1/);
});

test('completed readiness is cleared and Profile never combines its error with an endless spinner', () => {
  assert.match(api, /\.finally\(\(\)=>\{if\(backendReadyPromise===warmup\)backendReadyPromise=null\}\)/);
  assert.match(app, /:profileLoading\?<View[\s\S]*A carregar o perfil[\s\S]*<\/View>:null\}\{profileError\?<ErrorNotice/);
  assert.match(app, /setProfileLoading\(false\)/);
});

test('READY then sleeping backend starts a new warm-up before recovering the GET', () => {
  assert.doesNotMatch(api, /let backendReady\s*=/);
  assert.match(api, /if\(backendReadyPromise\)return backendReadyPromise/);
  assert.match(api, /const warmup=request\('\/health'/);
  assert.match(api, /finally[\s\S]*backendReadyPromise=null/);
  assert.match(api, /catch\(error\)[\s\S]*await ensureBackendReady\(\);[\s\S]*return request\(path,\{\.\.\.options,maxAttempts:1\}\)/);
});

test('writes wait for readiness but execute exactly once', () => {
  assert.match(api, /async function writeWhenReady[\s\S]*await ensureBackendReady\(\);\n\s*return request\(path,\{\.\.\.options,maxAttempts:1\}\)/);
  assert.match(api, /saveProfile:async[\s\S]*writeWhenReady\('\/profile'/);
  assert.doesNotMatch(api, /writeWhenReady[\s\S]*for\s*\(/);
});


test('Opportunity opens server-backed detail and never uses the stale card URL', () => {
  assert.match(api, /opportunity:async\(id\)=>normalizeOpportunity\(await readWhenReady\(`\/opportunities\/\$\{encodeURIComponent\(id\)\}`\)\)/);
  assert.match(app, /api\.opportunity\(item\.id\)\.then\(fresh=>/);
  assert.match(app, /setCurrent\(fresh\);setNote\(fresh\?\.workflow\?\.note\|\|''\);onChanged\(fresh\)/);
  assert.match(app, /let active=true[\s\S]*if\(!active\)return[\s\S]*return\(\)=>\{active=false\}/);
  assert.match(app, /if\(detailLoading\)return[\s\S]*A obter o detalhe atual/);
  assert.match(app, /if\(detailError\|\|!current\)return[\s\S]*onRetry=\{\(\)=>setDetailReload/);
  assert.match(app, /current\.url\?<Pressable style=\{s\.button\} onPress=\{\(\)=>Linking\.openURL\(current\.url\)\}/);
  assert.doesNotMatch(app, /item\.url\?<Pressable/);
});

test('Workflow updates only after one server-confirmed write and survives detail reload', () => {
  assert.match(api, /setWorkflow:\(id,status,note\)=>writeWhenReady\(`\/opportunities\/\$\{encodeURIComponent\(id\)\}\/workflow`,\{method:'POST',body:JSON\.stringify\(\{status,note:note\|\|null\}\)\}\)/);
  assert.match(app, /if\(busy\)return;setBusy\(true\);setErr\(''\);try\{const response=await api\.setWorkflow\(current\.id,next,nextNote\);const workflow=response\?\.workflow\|\|response;if\(!workflow\?\.status\)throw Error\('Resposta inválida'\);const value=\{\.\.\.current,workflow\};setCurrent\(value\);onChanged\(value\)\}catch/);
  assert.match(app, /catch\(e\)\{setErr\('Não foi possível guardar o acompanhamento\.'\)\}finally\{setBusy\(false\)\}/);
  assert.match(app, /api\.opportunity\(item\.id\)[\s\S]*setCurrent\(fresh\);setNote\(fresh\?\.workflow\?\.note\|\|''\)/);
  assert.match(api, /async function writeWhenReady[\s\S]*return request\(path,\{\.\.\.options,maxAttempts:1\}\)/);
});
