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
const tenantStorage = createTenantStorage(adapter, () => '2026-08-25T18:00:00.000Z');

await adapter.setItem(LEGACY_PRIVATE_KEYS[1], JSON.stringify({ items: [{ id: 'legacy-A' }] }));
await tenantStorage.bindTenant('ACCOUNT_A');
assert.equal(await adapter.getItem(LEGACY_PRIVATE_KEYS[1]), null, 'legacy global private cache must be purged');

await tenantStorage.setProfile('ACCOUNT_A', { account_id: 'ACCOUNT_A', name: 'A' });
await tenantStorage.setCache('ACCOUNT_A', { account_id: 'ACCOUNT_A', items: [{ id: 'A-1', account_id: 'ACCOUNT_A' }], stats: { account_id: 'ACCOUNT_A', total: 1 } });
assert.equal((await tenantStorage.getProfile('ACCOUNT_A')).name, 'A');
assert.equal((await tenantStorage.getCache('ACCOUNT_A')).items[0].id, 'A-1');

await tenantStorage.bindTenant('ACCOUNT_B');
assert.equal(await adapter.getItem(privateStorageKey('ACCOUNT_A', 'profile')), null, 'account change must purge A profile');
assert.equal(await adapter.getItem(privateStorageKey('ACCOUNT_A', 'opportunities-cache')), null, 'account change must purge A Radar cache');
assert.equal(await tenantStorage.getProfile('ACCOUNT_B'), null, 'B must not hydrate A profile while offline');
assert.equal(await tenantStorage.getCache('ACCOUNT_B'), null, 'B must not fall back to A Radar while offline/slow');
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), 'ACCOUNT_B');

await assert.rejects(
  tenantStorage.setProfile('ACCOUNT_B', { account_id: 'ACCOUNT_A', name: 'wrong tenant' }),
  /identity does not match/,
  'identity-mismatched profile must never enter B cache',
);

const bProfileKey = privateStorageKey('ACCOUNT_B', 'profile');
await adapter.setItem(bProfileKey, JSON.stringify({ accountId: 'ACCOUNT_A', kind: 'profile', value: { account_id: 'ACCOUNT_A', name: 'forged' } }));
assert.equal(await tenantStorage.getProfile('ACCOUNT_B'), null, 'hydration must validate the cache envelope identity');
assert.equal(await adapter.getItem(bProfileKey), null, 'mismatched cache must be purged instead of retained');

await tenantStorage.setCache('ACCOUNT_B', { items: [{ id: 'B-1', account_id: 'ACCOUNT_B' }] });
await tenantStorage.bindTenant(null);
assert.equal(await adapter.getItem(privateStorageKey('ACCOUNT_B', 'opportunities-cache')), null, 'sign-out must purge the active tenant cache');
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), null, 'sign-out must clear the active tenant binding');

console.log('PASS: tenant-scoped private cache blocks Account A -> Account B hydration/fallback');
console.log('PASS: account changes/sign-out purge and rebind private storage');
console.log('PASS: cache identity is validated before hydration');
