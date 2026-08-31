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
const store = createTenantStorage(adapter, () => '2026-08-31T00:00:00.000Z');
assert.ok(LEGACY_PRIVATE_KEYS.includes('@obrasignal/v1/settings'));
await adapter.setItem('@obrasignal/v1/settings', JSON.stringify({ notifications: true, source: 'legacy-a' }));
await store.bindTenant('USER-A');
assert.equal(await adapter.getItem('@obrasignal/v1/settings'), null);
await store.setSettings('USER-A', { notifications: true, minScore: 90, source: 'A' });
await store.setProfile('USER-A', { name: 'Account A' });
await store.setCache('USER-A', { items: [{ id: 'A-1' }] });
await store.bindTenant('USER-B');
assert.equal(await adapter.getItem(privateStorageKey('USER-A', 'settings')), null);
assert.equal(await adapter.getItem(privateStorageKey('USER-A', 'profile')), null);
assert.equal(await adapter.getItem(privateStorageKey('USER-A', 'opportunities-cache')), null);
assert.deepEqual(await store.getSettings('USER-B'), {});
assert.equal(await store.getProfile('USER-B'), null);
assert.equal(await store.getCache('USER-B'), null);
await store.setSettings('USER-B', { notifications: false, minScore: 60, source: 'B' });
const forged = privateStorageKey('USER-B', 'settings');
await adapter.setItem(forged, JSON.stringify({ identity: 'USER-A', kind: 'settings', value: { notifications: true } }));
assert.deepEqual(await store.getSettings('USER-B'), {});
assert.equal(await adapter.getItem(forged), null);
await store.setProfile('USER-B', { name: 'Account B' });
await store.bindTenant(null);
assert.equal(await adapter.getItem(privateStorageKey('USER-B', 'settings')), null);
assert.equal(await adapter.getItem(privateStorageKey('USER-B', 'profile')), null);
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), null);
console.log('PASS: current-main tenant-private storage blocks A -> B -> logout leakage');
