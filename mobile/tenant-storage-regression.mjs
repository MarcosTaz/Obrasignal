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
for (const key of LEGACY_PRIVATE_KEYS) await adapter.setItem(key, JSON.stringify({ legacy: true }));
await tenantStorage.bindTenant('ACCOUNT_A');
for (const key of LEGACY_PRIVATE_KEYS) assert.equal(await adapter.getItem(key), null, `${key} must be purged at tenant bind`);

await tenantStorage.setSaved('ACCOUNT_A', ['A-1']);
await tenantStorage.setSettings('ACCOUNT_A', { notifications: true, source: 'A' });
await tenantStorage.setCache('ACCOUNT_A', { items: [{ id: 'A-1' }] });
await tenantStorage.setProfile('ACCOUNT_A', { name: 'A' });

await tenantStorage.bindTenant('ACCOUNT_B');
for (const kind of ['saved', 'settings', 'opportunities-cache', 'profile']) {
  assert.equal(await adapter.getItem(privateStorageKey('ACCOUNT_A', kind)), null, `${kind} from A must be purged on switch`);
}
assert.deepEqual(await tenantStorage.getSaved('ACCOUNT_B'), []);
assert.deepEqual(await tenantStorage.getSettings('ACCOUNT_B'), {});
assert.equal(await tenantStorage.getCache('ACCOUNT_B'), null);
assert.equal(await tenantStorage.getProfile('ACCOUNT_B'), null);
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), 'ACCOUNT_B');

const forgedKey = privateStorageKey('ACCOUNT_B', 'settings');
await adapter.setItem(forgedKey, JSON.stringify({ identity: 'ACCOUNT_A', kind: 'settings', value: { notifications: true } }));
assert.deepEqual(await tenantStorage.getSettings('ACCOUNT_B'), {});
assert.equal(await adapter.getItem(forgedKey), null, 'forged cross-account envelope must be removed');

await tenantStorage.setProfile('ACCOUNT_B', { name: 'B' });
await tenantStorage.bindTenant(null);
assert.equal(await adapter.getItem(privateStorageKey('ACCOUNT_B', 'profile')), null, 'sign-out must purge B private state');
assert.equal(await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY), null);

console.log('PASS: all mobile customer cache/settings/profile state is tenant-private across A -> B -> sign-out');
