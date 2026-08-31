import AsyncStorage from '@react-native-async-storage/async-storage';
import { createTenantStorage } from './tenantStorage';

const KEYS = {
  saved: '@obrasignal/v1/saved',
  settings: '@obrasignal/v1/settings',
  cache: '@obrasignal/v1/opportunities-cache',
  profile: '@obrasignal/v1/profile',
  pushInstallation: '@obrasignal/v1/push-installation',
};

const DEFAULT_SETTINGS = {
  notifications: false,
  minScore: 75,
  openOnly: true,
  source: '',
};

function newInstallationId() {
  return `install-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}-${Math.random().toString(36).slice(2, 12)}`;
}

const privateStorage = createTenantStorage(AsyncStorage);
let activePrivateTenant = null;

function requirePrivateTenant() {
  if (!activePrivateTenant) throw new Error('Private storage is not bound to an authenticated account');
  return activePrivateTenant;
}

export const storage = {
  async bindPrivateTenant(accountId) {
    // Clear the in-memory binding before any async work so private reads fail
    // closed while an account transition is in progress.
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
  getSettings: () => activePrivateTenant ? privateStorage.getSettings(activePrivateTenant).then((settings) => ({ ...DEFAULT_SETTINGS, ...settings })) : Promise.resolve({ ...DEFAULT_SETTINGS }),
  setSettings: (settings) => privateStorage.setSettings(requirePrivateTenant(), settings),
  getCache: () => activePrivateTenant ? privateStorage.getCache(activePrivateTenant) : Promise.resolve(null),
  setCache: (payload) => privateStorage.setCache(requirePrivateTenant(), payload),
  getProfile: () => activePrivateTenant ? privateStorage.getProfile(activePrivateTenant) : Promise.resolve(null),
  setProfile: (profile) => privateStorage.setProfile(requirePrivateTenant(), profile),
  getPushBinding: () => activePrivateTenant ? privateStorage.getPushBinding(activePrivateTenant) : Promise.resolve(null),
  setPushBinding: (binding) => privateStorage.setPushBinding(requirePrivateTenant(), binding),
  clearPushBinding: () => activePrivateTenant ? privateStorage.clearPushBinding(activePrivateTenant) : Promise.resolve(),
  getLocalNotificationScheduled: () => activePrivateTenant ? privateStorage.getLocalNotificationScheduled(activePrivateTenant) : Promise.resolve([]),
  setLocalNotificationScheduled: (eventIds) => privateStorage.setLocalNotificationScheduled(requirePrivateTenant(), eventIds),
  async ensurePushInstallationId() {
    const current = (await AsyncStorage.getItem(KEYS.pushInstallation) || '').trim();
    if (current) return current;
    const generated = newInstallationId();
    await AsyncStorage.setItem(KEYS.pushInstallation, generated);
    return generated;
  },
};

export { KEYS, DEFAULT_SETTINGS };
