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
let initialSettingsWritePending = false;

function requirePrivateTenant() {
  if (!activePrivateTenant) throw new Error('Private storage is not bound to an authenticated account');
  return activePrivateTenant;
}

function isDefaultSettings(settings) {
  return Boolean(settings)
    && settings.notifications === DEFAULT_SETTINGS.notifications
    && settings.minScore === DEFAULT_SETTINGS.minScore
    && settings.openOnly === DEFAULT_SETTINGS.openOnly
    && (settings.source || '') === DEFAULT_SETTINGS.source;
}

async function mirrorNotificationPreference(settings) {
  if (typeof settings?.notifications !== 'boolean') return;
  try {
    const { syncPushPreference } = await import('./notifications');
    await syncPushPreference(settings.notifications);
  } catch (_) {
    // Local settings remain usable offline. Startup retries registration later.
  }
}

export const storage = {
  async bindPrivateTenant(accountId) {
    activePrivateTenant = null;
    initialSettingsWritePending = false;
    const next = await privateStorage.bindTenant(accountId);
    activePrivateTenant = next;
    initialSettingsWritePending = Boolean(next);
    return next;
  },
  async purgePrivateTenant(accountId = activePrivateTenant) {
    if (!accountId) return;
    await privateStorage.purgeTenant(accountId);
    if (activePrivateTenant === String(accountId).trim()) {
      activePrivateTenant = null;
      initialSettingsWritePending = false;
    }
  },
  getActivePrivateTenant: () => activePrivateTenant,

  getSaved: () => activePrivateTenant ? privateStorage.getSaved(activePrivateTenant) : Promise.resolve([]),
  setSaved: (ids) => privateStorage.setSaved(requirePrivateTenant(), ids),
  getSettings: () => activePrivateTenant
    ? privateStorage.getSettings(activePrivateTenant).then((settings) => ({ ...DEFAULT_SETTINGS, ...settings }))
    : Promise.resolve({ ...DEFAULT_SETTINGS }),
  async setSettings(settings) {
    requirePrivateTenant();
    // Main() mounts with DEFAULT_SETTINGS before its async hydration completes.
    // Never let that first render overwrite a returning customer's persisted
    // notification choice. The hydrated state (or a later user action) owns it.
    if (initialSettingsWritePending) {
      initialSettingsWritePending = false;
      if (isDefaultSettings(settings)) return;
    }
    await privateStorage.setSettings(activePrivateTenant, settings);
    await mirrorNotificationPreference(settings);
  },
  getCache: () => activePrivateTenant ? privateStorage.getCache(activePrivateTenant) : Promise.resolve(null),
  setCache: (payload) => privateStorage.setCache(requirePrivateTenant(), payload),
  getProfile: () => activePrivateTenant ? privateStorage.getProfile(activePrivateTenant) : Promise.resolve(null),
  setProfile: (profile) => privateStorage.setProfile(requirePrivateTenant(), profile),
};

export { DEFAULT_SETTINGS };
