import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('./src/tenantStorage.js', import.meta.url), 'utf8');
const { ACTIVE_PRIVATE_TENANT_KEY, LEGACY_PRIVATE_KEYS, createTenantStorage, privateStorageKey } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

class MemoryStorage {
  constructor() { this.values = new Map(); }
  async getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  async setItem(key, value) { this.values.set(key, String(value)); }
  async removeItem(key) { this.values.delete(key); }
}

const adapter = new MemoryStorage();
const tenantStorage = createTenantStorage(adapter, () => '2026-08-31T00:00:00.000Z');
const legacyCacheKey = '@obrasignal/v1/opportunities-cache';
const legacySettingsKey = '@obrasignal/v1/settings';
assert.equal(LEGACY_PRIVATE_KEYS.includes(legacyCacheKey), true, 'legacy global Radar cache must remain registered for purge');
assert.equal(LEGACY_PRIVATE_KEYS.includes(legacySettingsKey), true, 'legacy global settings must be registered for purge');

await adapter.setItem(legacyCacheKey, JSON.stringify({ items: [{ id: 'legacy-A' }] }));
await adapter.setItem(legacySettingsKey, JSON.stringify({ notifications: true, minScore: 1 }));
await tenantStorage.bindTenant('SESSION_A');
assert.equal(await adapter.getItem(legacyCacheKey), null, 'legacy global private cache must be purged');
assert.equal(await adapter.getItem(legacySettingsKey), null, 'legacy global settings must be purged before tenant hydration');

await tenantStorage.setProfile('SESSION_A', { account_id: 'BACKEND_TENANT_A', name: 'A' });
await tenantStorage.setCache('SESSION_A', { items: [{ id: 'A-1' }], stats: { total: 1 } });
await tenantStorage.setSettings('SESSION_A', { notifications: true, minScore: 90, openOnly: false, source: 'A-only' });
await tenantStorage.setPushBinding('SESSION_A', { bindingId: 'binding-a', installationId: 'install-device-001' });
assert.equal((await tenantStorage.getProfile('SESSION_A')).name, 'A');
assert.equal((await tenantStorage.getCache('SESSION_A')).items[0].id, 'A-1');
assert.deepEqual(await tenantStorage.getSettings('SESSION_A'), { notifications: true, minScore: 90, openOnly: false, source: 'A-only' });
assert.equal((await tenantStorage.getPushBinding('SESSION_A')).bindingId, 'binding-a');

await tenantStorage.bindTenant('SESSION_B');
assert.equal(await adapter.getItem(privateStorageKey('SESSION_A', 'profile')), null, 'identity change must purge A profile');
assert.equal(await adapter.getItem(privateStorageKey('SESSION_A', 'opportunities-cache')), null, 'identity change must purge A Radar cache');
assert.equal(await adapter.getItem(privateStorageKey('SESSION_A', 'settings')), null, 'identity change must purge A customer settings');
assert.equal(await adapter.getItem(privateStorageKey('SESSION_A', 'push-binding')), null, 'identity change must purge A notification binding');
assert.equal(await tenantStorage.getProfile('SESSION_B'), null, 'B must not hydrate A profile while offline');
assert.equal(await tenantStorage.getCache('SESSION_B'), null, 'B must not fall back to A Radar while offline/slow');
assert.deepEqual(await tenantStorage.getSettings('SESSION_B'), {}, 'B must not inherit A notification/filter/source preferences');
assert.equal(await tenantStorage.getPushBinding('SESSION_B'), null, 'B must not accept an Account A notification binding');
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), 'SESSION_B');

const bProfileKey = privateStorageKey('SESSION_B', 'profile');
await adapter.setItem(bProfileKey, JSON.stringify({ identity: 'SESSION_A', kind: 'profile', value: { account_id: 'BACKEND_TENANT_A', name: 'forged' } }));
assert.equal(await tenantStorage.getProfile('SESSION_B'), null, 'hydration must validate the cache envelope identity');
assert.equal(await adapter.getItem(bProfileKey), null, 'mismatched cache must be purged instead of retained');

const bSettingsKey = privateStorageKey('SESSION_B', 'settings');
await adapter.setItem(bSettingsKey, JSON.stringify({ identity: 'SESSION_A', kind: 'settings', value: { notifications: true, source: 'forged-a' } }));
assert.deepEqual(await tenantStorage.getSettings('SESSION_B'), {}, 'settings hydration must validate local session identity');
assert.equal(await adapter.getItem(bSettingsKey), null, 'mismatched settings envelope must be purged');

const bPushKey = privateStorageKey('SESSION_B', 'push-binding');
await adapter.setItem(bPushKey, JSON.stringify({ identity: 'SESSION_A', kind: 'push-binding', value: { bindingId: 'forged-a' } }));
assert.equal(await tenantStorage.getPushBinding('SESSION_B'), null, 'notification binding hydration must validate local session identity');
assert.equal(await adapter.getItem(bPushKey), null, 'mismatched notification binding must be purged');

await tenantStorage.setProfile('SESSION_B', { account_id: 'A_BACKEND_MAPPING_MAY_DIFFER', name: 'B' });
assert.equal((await tenantStorage.getProfile('SESSION_B')).name, 'B', 'local cache must not invent backend account mapping rules');

await tenantStorage.setCache('SESSION_B', { items: [{ id: 'B-1' }] });
await tenantStorage.setSettings('SESSION_B', { notifications: false, minScore: 70, openOnly: true, source: 'B-only' });
assert.equal((await tenantStorage.getSettings('SESSION_B')).source, 'B-only', 'B must own an independent settings envelope');
await tenantStorage.setPushBinding('SESSION_B', { bindingId: 'binding-b', installationId: 'install-device-001' });
assert.equal((await tenantStorage.getPushBinding('SESSION_B')).bindingId, 'binding-b');
await tenantStorage.clearPushBinding('SESSION_B');
assert.equal(await tenantStorage.getPushBinding('SESSION_B'), null, 'explicit notification disable must revoke the local tap binding');

await tenantStorage.setPushBinding('SESSION_B', { bindingId: 'binding-b2', installationId: 'install-device-001' });
await tenantStorage.bindTenant(null);
assert.equal(await adapter.getItem(privateStorageKey('SESSION_B', 'opportunities-cache')), null, 'sign-out must purge the active identity cache');
assert.equal(await adapter.getItem(privateStorageKey('SESSION_B', 'settings')), null, 'sign-out must purge the active identity settings');
assert.equal(await adapter.getItem(privateStorageKey('SESSION_B', 'push-binding')), null, 'sign-out must purge the active notification binding');
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), null, 'sign-out must clear the active identity binding');

console.log('PASS: tenant-scoped private cache blocks Account A -> Account B hydration/fallback');
console.log('PASS: account-scoped settings block Account A notification/filter/source preferences from leaking to B');
console.log('PASS: account changes/sign-out purge and rebind private storage including settings and notification binding');
console.log('PASS: explicit notification disable revokes tenant-private tap binding');
console.log('PASS: cache/settings/binding envelope identity is validated before hydration without duplicating backend Auth tenancy');
