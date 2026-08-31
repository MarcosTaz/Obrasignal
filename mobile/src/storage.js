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

function requirePrivateTenant() {
  if (!activePrivateTenant) throw new Error('Private storage is not bound to an authenticated account');
  return activePrivateTenant;
}

export const storage = {
  async bindPrivateTenant(accountId) {
    // Clear the in-memory binding immediately so an account switch cannot read
    // the previous account while AsyncStorage cleanup is still in progress.
    activePrivateTenant = null;
    const next = await privateStorage.bindTenant(accountId);
    activePrivateTenant = next;
    return next;
  },
  async purgePrivateTenant(accountId = activePrivateTenant) {
    if (!accountId) return;
    await privateStorage.purgeTenant(accountId);
    if (activePrivateTenant === String(accountId).trim()) activePrivateTenant = null;
  },
  getActivePrivateTenant: () => activePrivateTenant,

  getSaved: () => activePrivateTenant ? privateStorage.getSaved(activePrivateTenant) : Promise.resolve([]),
  setSaved: (ids) => privateStorage.setSaved(requirePrivateTenant(), ids),
  getSettings: () => activePrivateTenant
    ? privateStorage.getSettings(activePrivateTenant).then((settings) => ({ ...DEFAULT_SETTINGS, ...settings }))
    : Promise.resolve({ ...DEFAULT_SETTINGS }),
  setSettings: (settings) => privateStorage.setSettings(requirePrivateTenant(), settings),
  getCache: () => activePrivateTenant ? privateStorage.getCache(activePrivateTenant) : Promise.resolve(null),
  setCache: (payload) => privateStorage.setCache(requirePrivateTenant(), payload),
  getProfile: () => activePrivateTenant ? privateStorage.getProfile(activePrivateTenant) : Promise.resolve(null),
  setProfile: (profile) => privateStorage.setProfile(requirePrivateTenant(), profile),
};

export { DEFAULT_SETTINGS };
