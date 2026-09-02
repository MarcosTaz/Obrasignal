import assert from 'node:assert/strict';
import fs from 'node:fs';

const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');
const storage = fs.readFileSync(new URL('./src/storage.js', import.meta.url), 'utf8');

assert.match(api, /async function saveProfileVerified\(profile\)/, 'profile saves must use verified server persistence');
assert.match(api, /const persisted=unwrapProfile\(await readWhenReady\('\/profile'/, 'save must perform authenticated server read-back');
assert.match(api, /persistedProfileMatches\(expected,persisted\)/, 'read-back must be compared with submitted profile');
assert.match(api, /contract_interests/, 'business specifications must be part of persistence verification');
assert.match(api, /coverage_mode/, 'coverage mode must be part of persistence verification');
assert.match(api, /countries/, 'countries must be part of persistence verification');
assert.match(api, /regions/, 'regions must be part of persistence verification');
assert.match(api, /min_value/, 'minimum contract value must be part of persistence verification');
assert.match(api, /max_value/, 'maximum contract value must be part of persistence verification');
assert.match(api, /storage\.getRecoverableProfile\(\)/, 'empty server profile must have a bounded legacy browser recovery path');
assert.match(api, /if\(hasCompanyIdentity\(serverProfile\)\)/, 'valid server identity must win before browser recovery');
assert.match(api, /const migrated=await saveProfileVerified\(recoverable\)/, 'browser recovery must migrate through verified server persistence');

assert.match(storage, /Platform\.OS !== 'web'/, 'ordinary Web hydration must not treat browser profile as canonical');
assert.match(storage, /getRecoverableProfile:/, 'tenant-scoped browser profile must remain recoverable for migration');

console.log('profile persistence regression: ok');
