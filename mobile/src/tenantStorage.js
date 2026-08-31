export const PRIVATE_STORAGE_PREFIX = '@obrasignal/v2/private';
export const ACTIVE_PRIVATE_TENANT_KEY = '@obrasignal/v2/private-tenant';
export const LEGACY_PRIVATE_KEYS = [
  '@obrasignal/v1/saved',
  '@obrasignal/v1/settings',
  '@obrasignal/v1/opportunities-cache',
  '@obrasignal/v1/profile',
];

const PRIVATE_KINDS = ['saved', 'settings', 'opportunities-cache', 'profile'];

function normalizeIdentity(identity) {
  const value = String(identity || '').trim();
  if (!value) throw new Error('authenticated identity is required for private storage');
  return value;
}

export function privateStorageKey(identity, kind) {
  if (!PRIVATE_KINDS.includes(kind)) throw new Error(`Unsupported private storage kind: ${kind}`);
  return `${PRIVATE_STORAGE_PREFIX}/${encodeURIComponent(normalizeIdentity(identity))}/${kind}`;
}

async function purgeKind(adapter, identity, kind) {
  await adapter.removeItem(privateStorageKey(identity, kind));
}

export function createTenantStorage(adapter, now = () => new Date().toISOString()) {
  async function purgeTenant(identity) {
    const tenant = normalizeIdentity(identity);
    await Promise.all(PRIVATE_KINDS.map((kind) => purgeKind(adapter, tenant, kind)));
  }

  async function readPrivate(identity, kind, fallback) {
    const tenant = normalizeIdentity(identity);
    const key = privateStorageKey(tenant, kind);
    try {
      const raw = await adapter.getItem(key);
      if (!raw) return fallback;
      const envelope = JSON.parse(raw);
      if (!envelope || envelope.identity !== tenant || envelope.kind !== kind || !Object.prototype.hasOwnProperty.call(envelope, 'value')) {
        await adapter.removeItem(key);
        return fallback;
      }
      return envelope.value;
    } catch (_) {
      try { await adapter.removeItem(key); } catch (_) {}
      return fallback;
    }
  }

  async function writePrivate(identity, kind, value) {
    const tenant = normalizeIdentity(identity);
    await adapter.setItem(privateStorageKey(tenant, kind), JSON.stringify({ identity: tenant, kind, value, cachedAt: now() }));
  }

  async function bindTenant(identity) {
    const next = identity == null ? null : normalizeIdentity(identity);
    const previousRaw = await adapter.getItem(ACTIVE_PRIVATE_TENANT_KEY);
    const previous = previousRaw ? String(previousRaw).trim() : null;
    await Promise.all(LEGACY_PRIVATE_KEYS.map((key) => adapter.removeItem(key)));
    if (previous && previous !== next) await purgeTenant(previous);
    if (!next) {
      if (previous) await purgeTenant(previous);
      await adapter.removeItem(ACTIVE_PRIVATE_TENANT_KEY);
      return null;
    }
    await adapter.setItem(ACTIVE_PRIVATE_TENANT_KEY, next);
    return next;
  }

  return {
    bindTenant,
    purgeTenant,
    getSaved: (identity) => readPrivate(identity, 'saved', []),
    setSaved: (identity, ids) => writePrivate(identity, 'saved', ids),
    getSettings: (identity) => readPrivate(identity, 'settings', {}),
    setSettings: (identity, settings) => writePrivate(identity, 'settings', settings),
    getCache: (identity) => readPrivate(identity, 'opportunities-cache', null),
    setCache: (identity, payload) => writePrivate(identity, 'opportunities-cache', payload),
    getProfile: (identity) => readPrivate(identity, 'profile', null),
    setProfile: (identity, profile) => writePrivate(identity, 'profile', profile),
  };
}
