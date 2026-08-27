import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { api } from './api';
import { storage } from './storage';

const EXPO_PROJECT_ID = 'c277466b-a418-45f7-b070-4fc3f96386b7';
const handledResponseIds = new Set();
const MAX_LOCAL_SCHEDULED_EVENT_IDS = 100;

function newLocalBindingId() {
  return `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}-${Math.random().toString(36).slice(2, 14)}`;
}

function isRemoteBinding(binding) {
  return Boolean(binding?.bindingId && binding?.installationId && binding?.expoPushToken);
}

function normalizeScheduledEventIds(values) {
  const ids = [];
  for (const value of Array.isArray(values) ? values : []) {
    const id = Number(value);
    if (Number.isInteger(id) && id > 0 && !ids.includes(id)) ids.push(id);
  }
  return ids.slice(-MAX_LOCAL_SCHEDULED_EVENT_IDS);
}

async function rememberLocalScheduledEvent(eventId) {
  const id = Number(eventId);
  if (!Number.isInteger(id) || id <= 0) return;
  const current = normalizeScheduledEventIds(await storage.getLocalNotificationScheduled());
  if (current.includes(id)) return;
  await storage.setLocalNotificationScheduled([...current, id].slice(-MAX_LOCAL_SCHEDULED_EVENT_IDS));
}

async function forgetLocalScheduledEvent(eventId) {
  const id = Number(eventId);
  if (!Number.isInteger(id) || id <= 0) return;
  const current = normalizeScheduledEventIds(await storage.getLocalNotificationScheduled());
  if (!current.includes(id)) return;
  await storage.setLocalNotificationScheduled(current.filter(value => value !== id));
}

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
  // A tenant change purges the old private binding in #291. With no current
  // binding, dismiss any stale previously-presented tray immediately before
  // attempting a new provider binding.
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

  // A valid local-only fallback remains authoritative while provider registration
  // is unavailable. Dismiss it only after remote registration has actually
  // succeeded, immediately before replacing its tap authority.
  if (existingBinding && !isRemoteBinding(existingBinding)) {
    try { await Notifications.dismissAllNotificationsAsync(); } catch (_) {}
  }
  await storage.setPushBinding({ bindingId, installationId, expoPushToken, kind: 'remote' });
  return { status: 'registered', registered: true, bindingId, installationId };
}

export async function unregisterRemoteOpportunityPush() {
  if (Platform.OS === 'web') return;
  const binding = await storage.getPushBinding();
  // Local tap authority is revoked before any network call. A slow/offline
  // unregister cannot leave a disabled or signed-out account locally tap-valid.
  try { await storage.clearPushBinding(); } catch (_) {}
  try { await storage.setLocalNotificationScheduled([]); } catch (_) {}
  try {
    if (binding?.installationId) await api.unregisterPushDevice(binding.installationId);
  } finally {
    try { await Notifications.dismissAllNotificationsAsync(); } catch (_) {}
  }
}

export async function showLocalOpportunityAlert(item) {
  if (Platform.OS === 'web') return null;
  let binding = await storage.getPushBinding();
  if (!binding?.bindingId) {
    // Local fallback still needs tenant-bound tap authority. Never emit an
    // unbound local notification merely because remote FCM/EAS is unavailable.
    binding = { bindingId: newLocalBindingId(), kind: 'local' };
    await storage.setPushBinding(binding);
  }
  return Notifications.scheduleNotificationAsync({
    content: {
      title: 'Nova oportunidade ObraSignal',
      // Keep the OS tray tenant-neutral just like remote push. Opportunity truth
      // is fetched only after the current private binding validates the tap.
      body: 'Abre o ObraSignal para confirmar uma nova oportunidade.',
      data: { opportunityId: item?.id, eventId: item?.event_id, bindingId: binding.bindingId },
      ...(Platform.OS === 'android' ? { channelId: 'opportunities' } : {}),
    },
    trigger: null,
  });
}

export async function syncUnreadOpportunityAlerts() {
  if (Platform.OS === 'web') return { status: 'unsupported', scheduled: 0 };
  const settings = await storage.getSettings();
  if (!settings.notifications) return { status: 'disabled', scheduled: 0 };

  const granted = await configureNotifications();
  if (!granted) return { status: 'permission_denied', scheduled: 0 };

  const result = await api.alerts({ unreadOnly: true, limit: 10 });
  const items = result?.items || [];
  const alreadyScheduled = new Set(normalizeScheduledEventIds(await storage.getLocalNotificationScheduled()));
  let scheduled = 0;

  for (const item of items) {
    const eventId = Number(item?.event_id);
    if (Number.isInteger(eventId) && eventId > 0 && alreadyScheduled.has(eventId)) continue;
    try {
      await showLocalOpportunityAlert(item);
      // Scheduling acceptance is only local pending evidence. It must not write
      // opportunity_events.delivered_at. User response/tap below is the first
      // current path with direct user-observation authority.
      if (Number.isInteger(eventId) && eventId > 0) {
        await rememberLocalScheduledEvent(eventId);
        alreadyScheduled.add(eventId);
      }
      scheduled += 1;
    } catch (_) {
      // Keep the server event unread and do not persist local scheduling evidence
      // when scheduling itself fails so a later verification may retry.
    }
  }

  return { status: 'ready', scheduled };
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
    try {
      await api.markAlertDelivered(eventId);
      await forgetLocalScheduledEvent(eventId);
    } catch (_) {
      // The tap is consumed locally, but server completion remains unproven.
      // Retain local scheduled evidence so a transient server failure does not
      // immediately re-present the same unread event as a new notification.
    }
  }
  return opportunityId;
}

export function listenForOpportunityNotificationResponses(onTarget) {
  if (Platform.OS === 'web') return () => {};
  let active = true;
  const clearLastResponse = async () => {
    try { await Notifications.clearLastNotificationResponseAsync(); } catch (_) {}
  };
  const handle = async (response) => {
    const responseId = String(response?.notification?.request?.identifier || '').trim();
    if (responseId && handledResponseIds.has(responseId)) {
      // A remount can reread the same native last response after a live listener
      // already consumed it. Clear native state before returning so a later app
      // process cannot replay it after the in-memory Set is lost.
      await clearLastResponse();
      return;
    }
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
      await clearLastResponse();
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
