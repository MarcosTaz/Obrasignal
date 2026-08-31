import AsyncStorage from '@react-native-async-storage/async-storage';
import { createTenantStorage } from './tenantStorage';

const DEFAULT_SETTINGS = {
  notifications: false,
  minScore: 75,
  openOnly: true,
  source: '',
};

const privateStorage = createTenantStorage(AsyncStorage);
let activePrivateTenant = null;
let bindingQueue = Promise.resolve();

function requirePrivateTenant() {
  if (!activePrivateTenant) throw new Error('Private storage is not bound to an authenticated account');
  return activePrivateTenant;
}

export const storage = {
  bindPrivateTenant(accountId) {
    activePrivateTenant = null;
    const run = async () => {
      const next = await privateStorage.bindTenant(accountId);
      activePrivateTenant = next;
      return next;
    };
    bindingQueue = bindingQueue.then(run, run);
    return bindingQueue;
  },
  getActivePrivateTenant: () => activePrivateTenant,
  getSaved: () => activePrivateTenant ? privateStorage.getSaved(activePrivateTenant) : Promise.resolve([]),
  setSaved: (ids) => privateStorage.setSaved(requirePrivateTenant(), ids),
  getSettings: () => activePrivateTenant ? privateStorage.getSettings(activePrivateTenant).then((settings) => ({ ...DEFAULT_SETTINGS, ...settings })) : Promise.resolve({ ...DEFAULT_SETTINGS }),
  setSettings: (settings) => privateStorage.setSettings(requirePrivateTenant(), settings),
  getCache: () => activePrivateTenant ? privateStorage.getCache(activePrivateTenant) : Promise.resolve(null),
  setCache: (payload) => privateStorage.setCache(requirePrivateTenant(), { ...payload, cachedAt: new Date().toISOString() }),
  getProfile: () => activePrivateTenant ? privateStorage.getProfile(activePrivateTenant) : Promise.resolve(null),
  setProfile: (profile) => privateStorage.setProfile(requirePrivateTenant(), profile),
};

export { DEFAULT_SETTINGS };
