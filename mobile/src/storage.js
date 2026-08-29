import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS = {
  saved: '@obrasignal/v1/saved',
  settings: '@obrasignal/v1/settings',
  cache: '@obrasignal/v1/opportunities-cache',
  profile: '@obrasignal/v1/profile',
};

const DEFAULT_SETTINGS = {
  notifications: false,
  minScore: 75,
  openOnly: true,
  source: '',
};

let activeAccountScope = null;

function normalizeAccountScope(accountId) {
  const value = String(accountId || '').trim();
  return value || null;
}

function scopedStorageKey(baseKey, accountId = activeAccountScope) {
  const scope = normalizeAccountScope(accountId);
  return scope ? `${baseKey}/${encodeURIComponent(scope)}` : null;
}

async function readJson(key, fallback) {
  if (!key) return fallback;
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) { return fallback; }
}

async function readScopedJson(baseKey, fallback) {
  const scope = activeAccountScope;
  const key = scopedStorageKey(baseKey, scope);
  if (!scope || !key) return fallback;
  const value = await readJson(key, fallback);
  // A logout/account switch may happen while AsyncStorage is resolving. Never
  // return data read under an identity that is no longer active.
  return activeAccountScope === scope ? value : fallback;
}

function writeScopedJson(baseKey, value) {
  const scope = activeAccountScope;
  const key = scopedStorageKey(baseKey, scope);
  if (!scope || !key) return Promise.reject(new Error('account_scope_required'));
  // The key is captured synchronously from the current authenticated subject,
  // so a later account switch cannot redirect this write into the new account.
  return AsyncStorage.setItem(key, JSON.stringify(value));
}

export const storage = {
  setAccountScope(accountId) {
    activeAccountScope = normalizeAccountScope(accountId);
    return activeAccountScope;
  },
  getAccountScope: () => activeAccountScope,
  getSaved: () => readScopedJson(KEYS.saved, []),
  setSaved: (ids) => writeScopedJson(KEYS.saved, ids),
  getSettings: async () => ({ ...DEFAULT_SETTINGS, ...(await readScopedJson(KEYS.settings, {})) }),
  setSettings: (settings) => writeScopedJson(KEYS.settings, settings),
  getCache: () => readScopedJson(KEYS.cache, null),
  setCache: (payload) => writeScopedJson(KEYS.cache, { ...payload, cachedAt: new Date().toISOString() }),
  getProfile: () => readScopedJson(KEYS.profile, null),
  setProfile: (profile) => writeScopedJson(KEYS.profile, profile),
};

export { KEYS, DEFAULT_SETTINGS, scopedStorageKey };
