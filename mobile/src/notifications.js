import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { api } from './api';
import { storage } from './storage';

const EXPO_PROJECT_ID = 'c277466b-a418-45f7-b070-4fc3f96386b7';
const handledResponseIds = new Set();

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
  if (Platform.OS === 'web') return { status: 'unsupported', registered: false, reason: 'web' };
  const granted = await configureNotifications();
  if (!granted) {
    // Permission truth is independent from registration truth. If permission was
    // revoked after an earlier registration, invalidate that binding locally and
    // make a bounded best-effort server revoke rather than leaving it tap-valid.
    await unregisterRemoteOpportunityPush().catch(() => {});
    return { status: 'permission_denied', registered: false, reason: 'permission' };
  }

  const existingBinding = await storage.getPushBinding();
  // A tenant change purges the old private binding in #291. Clear any already
  // presented notifications before binding this installation to the new tenant.
  if (!existingBinding) {
    try { await Notifications.dismissAllNotificationsAsync(); } catch (_) {}
  }

  const tokenResult = await Notifications.getExpoPushTokenAsync({ projectId: EXPO_PROJECT_ID });
  const expoPushToken = String(tokenResult?.data || '').trim();
  if (!expoPushToken) return { status: 'remote_unavailable', registered: false, reason: 'token' };
  const installationId = await storage.ensurePushInstallationId();
  const response = await api.registerPushDevice({ installationId, expoPushToken, platform: Platform.OS });
  const bindingId = String(response?.binding_id || '').trim();
  if (!bindingId) throw new Error('push_binding_missing');
  await storage.setPushBinding({ bindingId, installationId, expoPushToken });
  return { status: 'registered', registered: true, bindingId, installationId };
}

export async function unregisterRemoteOpportunityPush() {
  if (Platform.OS === 'web') return;
  const binding = await storage.getPushBinding();
  // Local tap authority is revoked before any network call. A slow/offline
  // unregister cannot leave a disabled or signed-out account locally tap-valid.
  try { await storage.clearPushBinding(); } catch (_) {}
  try {
    if (binding?.installationId) await api.unregisterPushDevice(binding.installationId);
  } finally {
    try { await Notifications.dismissAllNotificationsAsync(); } catch (_) {}
  }
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
  if (Platform.OS === 'web') return { status: 'unsupported', delivered: 0 };
  const settings = await storage.getSettings();
  if (!settings.notifications) return { status: 'disabled', delivered: 0 };

  const granted = await configureNotifications();
  if (!granted) return { status: 'permission_denied', delivered: 0 };

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

  return { status: 'ready', delivered };
}

export async function notificationOpportunityTarget(response) {
  const data = response?.notification?.request?.content?.data || {};
  const opportunityId = Number(data.opportunityId);
  const eventId = Number(data.eventId);
  const bindingId = String(data.bindingId || '').trim();
  if (!Number.isInteger(opportunityId) || opportunityId <= 0 || !bindingId) return null;

  // A user-level notification disable is itself a fail-closed navigation gate,
  // even if physical storage cleanup or server revoke previously failed.
  const settings = await storage.getSettings();
  if (!settings.notifications) return null;

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
    const responseId = String(response?.notification?.request?.identifier || '').trim();
    if (responseId && handledResponseIds.has(responseId)) return;
    // Claim the native response before any async storage/API work so the initial
    // response and live listener cannot race into duplicate navigation.
    if (responseId) handledResponseIds.add(responseId);
    try {
      const opportunityId = await notificationOpportunityTarget(response);
      if (!active || !opportunityId) return;
      onTarget(opportunityId);
    } catch (_) {
      // A response is intentionally consumed fail-closed. It must not become
      // tap-valid later merely because a different tenant/session is mounted.
    } finally {
      // Expo persists the most recent response across startup. Consume it after
      // one validation attempt so a future process/remount cannot replay an old
      // tap without a new user interaction.
      try { await Notifications.clearLastNotificationResponseAsync(); } catch (_) {}
    }
  };
  const subscription = Notifications.addNotificationResponseReceivedListener(handle);
  Notifications.getLastNotificationResponseAsync().then((response) => {
    if (response) handle(response);
  }).catch(() => {});
  return () => {
    active = false;
    subscription.remove();
  };
}
