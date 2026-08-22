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
  assert.match(api, /profile:async\(\)=>unwrapProfile\(await request\('\/profile'/);
  assert.doesNotMatch(api, /profile:async\(\)=>\{try[\s\S]*storage\.getProfile/);
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
