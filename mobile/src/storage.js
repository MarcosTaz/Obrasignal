import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS = {
  saved: '@obrasignal/v1/saved',
  settings: '@obrasignal/v1/settings',
  cache: '@obrasignal/v1/opportunities-cache',
};

const DEFAULT_SETTINGS = {
  notifications: false,
  minScore: 75,
  openOnly: true,
  source: '',
};

async function readJson(key, fallback) {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) { return fallback; }
}

export const storage = {
  getSaved: () => readJson(KEYS.saved, []),
  setSaved: (ids) => AsyncStorage.setItem(KEYS.saved, JSON.stringify(ids)),
  getSettings: async () => ({ ...DEFAULT_SETTINGS, ...(await readJson(KEYS.settings, {})) }),
  setSettings: (settings) => AsyncStorage.setItem(KEYS.settings, JSON.stringify(settings)),
  getCache: () => readJson(KEYS.cache, null),
  setCache: (payload) => AsyncStorage.setItem(KEYS.cache, JSON.stringify({ ...payload, cachedAt: new Date().toISOString() })),
};

export { KEYS, DEFAULT_SETTINGS };
