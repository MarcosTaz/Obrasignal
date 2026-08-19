import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { api } from './api';
import { storage } from './storage';

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
