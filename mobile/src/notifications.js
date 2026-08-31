import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { api } from './api';
import { storage } from './storage';

const MORNING_HOUR = 8;
const MORNING_MINUTE = 0;
export const PUSH_TOKEN_STORAGE_KEY = '@obrasignal/push-token-v1';

if (Platform.OS !== 'web') {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });

  // Expo tokens can rotate. Rebind a rotated token to the authenticated tenant
  // immediately while the app is running; the next startup is a second retry.
  Notifications.addPushTokenListener(async (nextToken) => {
    try {
      const token = nextToken?.data;
      if (!token) return;
      await AsyncStorage.setItem(PUSH_TOKEN_STORAGE_KEY, token);
      const timezone = deviceTimezone();
      await api.registerPushDevice({ token, platform: Platform.OS, timezone });
    } catch (_) {}
  });
}

function deviceTimezone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Lisbon'; }
  catch (_) { return 'Europe/Lisbon'; }
}

function easProjectId() {
  return Constants?.expoConfig?.extra?.eas?.projectId ?? Constants?.easConfig?.projectId ?? null;
}

async function ensureNotificationPermission() {
  if (Platform.OS === 'web') return false;
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('opportunities', {
      name: 'Oportunidades',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 200],
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
      sound: 'default',
    });
  }
  const current = await Notifications.getPermissionsAsync();
  if (current.granted || current.ios?.status === Notifications.IosAuthorizationStatus?.PROVISIONAL) return true;
  const requested = await Notifications.requestPermissionsAsync();
  return Boolean(requested.granted || requested.ios?.status === Notifications.IosAuthorizationStatus?.PROVISIONAL);
}

async function registerServerPushDevice() {
  if (Platform.OS === 'web') return false;
  const projectId = easProjectId();
  if (!projectId) throw new Error('push_project_id_missing');
  const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
  if (!token) throw new Error('push_token_missing');
  await AsyncStorage.setItem(PUSH_TOKEN_STORAGE_KEY, token);
  const timezone = deviceTimezone();
  await api.setPushPreference({ enabled: true, timezone, local_hour: MORNING_HOUR, local_minute: MORNING_MINUTE });
  await api.registerPushDevice({ token, platform: Platform.OS, timezone });
  return true;
}

export async function syncPushPreference(enabled) {
  if (Platform.OS === 'web') return false;
  const timezone = deviceTimezone();
  if (!enabled) {
    await api.setPushPreference({ enabled: false, timezone, local_hour: MORNING_HOUR, local_minute: MORNING_MINUTE });
    return false;
  }
  const granted = await ensureNotificationPermission();
  if (!granted) {
    await api.setPushPreference({ enabled: false, timezone, local_hour: MORNING_HOUR, local_minute: MORNING_MINUTE }).catch(() => {});
    return false;
  }
  return registerServerPushDevice();
}

export async function configureNotifications() {
  if (Platform.OS === 'web') return false;
  const granted = await ensureNotificationPermission();
  if (!granted) return false;
  await registerServerPushDevice();
  return true;
}

export async function showLocalOpportunityAlert(item) {
  if (Platform.OS === 'web') return null;
  return Notifications.scheduleNotificationAsync({
    content: {
      title: 'Nova oportunidade ObraSignal',
      body: item?.title || 'Foi encontrada uma oportunidade relevante.',
      data: { opportunityId: item?.id, eventId: item?.event_id },
      ...(Platform.OS === 'android' ? { channelId: 'opportunities' } : {}),
    },
    trigger: null,
  });
}

export async function syncUnreadOpportunityAlerts() {
  if (Platform.OS === 'web') return 0;
  const settings = await storage.getSettings();
  if (!settings.notifications) return 0;

  const granted = await configureNotifications();
  if (!granted) return 0;

  // This immediate in-app sync is supplemental. The morning digest is sent by
  // the server and does not depend on this code running or the app being open.
  const result = await api.alerts({ unreadOnly: true, limit: 10 });
  const items = result?.items || [];
  let delivered = 0;

  for (const item of items) {
    try {
      await showLocalOpportunityAlert(item);
      if (item.event_id != null) await api.markAlertDelivered(item.event_id);
      delivered += 1;
    } catch (_) {
      // Keep the server event unread when local delivery fails so it can retry.
    }
  }

  return delivered;
}
