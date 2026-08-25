import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { api } from './api';
import { storage } from './storage';

const EXPO_PROJECT_ID = 'c277466b-a418-45f7-b070-4fc3f96386b7';

if (Platform.OS !== 'web') {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: true,
    }),
  });
}

export async function configureNotifications() {
  if (Platform.OS === 'web') return false;
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('opportunities', {
      name: 'Oportunidades',
      importance: Notifications.AndroidImportance.DEFAULT,
      vibrationPattern: [0, 200],
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
    });
  }
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return true;
  const requested = await Notifications.requestPermissionsAsync();
  return requested.granted;
}

export async function registerRemoteOpportunityPush() {
  if (Platform.OS === 'web') return { registered: false, reason: 'web' };
  const granted = await configureNotifications();
  if (!granted) return { registered: false, reason: 'permission' };

  const existingBinding = await storage.getPushBinding();
  // A tenant change purges the old private binding in #291. Clear any already
  // presented notifications before binding this installation to the new tenant.
  if (!existingBinding) {
    try { await Notifications.dismissAllNotificationsAsync(); } catch (_) {}
  }

  const tokenResult = await Notifications.getExpoPushTokenAsync({ projectId: EXPO_PROJECT_ID });
  const expoPushToken = String(tokenResult?.data || '').trim();
  if (!expoPushToken) return { registered: false, reason: 'token' };
  const installationId = await storage.ensurePushInstallationId();
  const response = await api.registerPushDevice({ installationId, expoPushToken, platform: Platform.OS });
  const bindingId = String(response?.binding_id || '').trim();
  if (!bindingId) throw new Error('push_binding_missing');
  await storage.setPushBinding({ bindingId, installationId, expoPushToken });
  return { registered: true, bindingId, installationId };
}

export async function showLocalOpportunityAlert(item) {
  if (Platform.OS === 'web') return null;
  const binding = await storage.getPushBinding();
  return Notifications.scheduleNotificationAsync({
    content: {
      title: 'Nova oportunidade ObraSignal',
      body: item?.title || 'Foi encontrada uma oportunidade relevante.',
      data: { opportunityId: item?.id, eventId: item?.event_id, bindingId: binding?.bindingId || null },
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

export async function notificationOpportunityTarget(response) {
  const data = response?.notification?.request?.content?.data || {};
  const opportunityId = Number(data.opportunityId);
  const eventId = Number(data.eventId);
  const bindingId = String(data.bindingId || '').trim();
  if (!Number.isInteger(opportunityId) || opportunityId <= 0 || !bindingId) return null;

  const current = await storage.getPushBinding();
  if (!current?.bindingId || current.bindingId !== bindingId) {
    // Stale Account A notification under Account B: fail closed and do not
    // even request the opportunity with B credentials.
    return null;
  }
  if (Number.isInteger(eventId) && eventId > 0) {
    try { await api.markAlertDelivered(eventId); } catch (_) {}
  }
  return opportunityId;
}

export function listenForOpportunityNotificationResponses(onTarget) {
  if (Platform.OS === 'web') return () => {};
  let active = true;
  const handle = async (response) => {
    try {
      const opportunityId = await notificationOpportunityTarget(response);
      if (active && opportunityId) onTarget(opportunityId);
    } catch (_) {}
  };
  const subscription = Notifications.addNotificationResponseReceivedListener(handle);
  Notifications.getLastNotificationResponseAsync().then(handle).catch(() => {});
  return () => {
    active = false;
    subscription.remove();
  };
}
