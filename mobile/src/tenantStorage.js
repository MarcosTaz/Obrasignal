export const PRIVATE_STORAGE_PREFIX = '@obrasignal/v2/private';
export const ACTIVE_PRIVATE_TENANT_KEY = '@obrasignal/v2/private-tenant';
export const LEGACY_PRIVATE_KEYS = [
  '@obrasignal/v1/saved',
  '@obrasignal/v1/opportunities-cache',
  '@obrasignal/v1/profile',
];

const PRIVATE_KINDS = ['saved', 'opportunities-cache', 'profile'];

function normalizeAccountId(accountId) {
  const value = String(accountId || '').trim();
  if (!value) throw new Error('account_id is required for private storage');
  return value;
}

export function privateStorageKey(accountId, kind) {
  if (!PRIVATE_KINDS.includes(kind)) throw new Error(`Unsupported private storage kind: ${kind}`);
  return `${PRIVATE_STORAGE_PREFIX}/${encodeURIComponent(normalizeAccountId(accountId))}/${kind}`;
}

function identityCandidates(kind, value) {
  if (!value || typeof value !== 'object') return [];
  if (kind === 'profile') return [value.account_id];
  if (kind === 'opportunities-cache') {
    return [
      value.account_id,
      value.stats?.account_id,
      ...(Array.isArray(value.items) ? value.items.map((item) => item?.account_id) : []),
    ];
  }
  return [];
}

function assertValueIdentity(accountId, kind, value) {
  const tenant = normalizeAccountId(accountId);
  for (const candidate of identityCandidates(kind, value)) {
    if (candidate == null || String(candidate).trim() === '') continue;
    if (String(candidate).trim() !== tenant) throw new Error(`Private ${kind} identity does not match the active account`);
  }
}

async function purgeKind(adapter, accountId, kind) {
  await adapter.removeItem(privateStorageKey(accountId, kind));
}

export function createTenantStorage(adapter, now = () => new Date().toISOString()) {
  async function purgeTenant(accountId) {
    const tenant = normalizeAccountId(accountId);
    await Promise.all(PRIVATE_KINDS.map((kind) => purgeKind(adapter, tenant, kind)));
  }

  async function readPrivate(accountId, kind, fallback) {
    const tenant = normalizeAccountId(accountId);
    const key = privateStorageKey(tenant, kind);
    try {
      const raw = await adapter.getItem(key);
      if (!raw) return fallback;
      const envelope = JSON.parse(raw);
      if (!envelope || envelope.accountId !== tenant || envelope.kind !== kind || !Object.prototype.hasOwnProperty.call(envelope, 'value')) {
        await adapter.removeItem(key);
        return fallback;
      }
      assertValueIdentity(tenant, kind, envelope.value);
      return envelope.value;
    } catch (_) {
      try { await adapter.removeItem(key); } catch (_) {}
      return fallback;
    }
  }

  async function writePrivate(accountId, kind, value) {
    const tenant = normalizeAccountId(accountId);
    assertValueIdentity(tenant, kind, value);
    const envelope = { accountId: tenant, kind, value, cachedAt: now() };
    await adapter.setItem(privateStorageKey(tenant, kind), JSON.stringify(envelope));
  }

  async function bindTenant(accountId) {
    const next = accountId == null ? null : normalizeAccountId(accountId);
    const previousRaw = await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY);
    const previous = previousRaw ? String(previousRaw).trim() : null;

    // Pre-v2 global keys may contain another account's private state. They are
    // never read by this implementation and are purged at every identity bind.
    await Promise.all(LEGACY_PRIVATE_KEYS.map((key) => adapter.removeItem(key)));

    if (previous && previous !== next) await purgeTenant(previous);
    if (!next) {
      await adapter.removeItem(ACTIVE_PRIVATE_TENANT_KEY);
      return null;
    }
    await adapter.setItem(ACTIVE_PRIVATE_TENANT_KEY, next);
    return next;
  }

  return {
    bindTenant,
    purgeTenant,
    getSaved: (accountId) => readPrivate(accountId, 'saved', []),
    setSaved: (accountId, ids) => writePrivate(accountId, 'saved', ids),
    getCache: (accountId) => readPrivate(accountId, 'opportunities-cache', null),
    setCache: (accountId, payload) => writePrivate(accountId, 'opportunities-cache', payload),
    getProfile: (accountId) => readPrivate(accountId, 'profile', null),
    setProfile: (accountId, profile) => writePrivate(accountId, 'profile', profile),
  };
}
