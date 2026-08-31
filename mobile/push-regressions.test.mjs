import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');
const storage = fs.readFileSync(new URL('./src/storage.js', import.meta.url), 'utf8');
const supabase = fs.readFileSync(new URL('./lib/supabase.ts', import.meta.url), 'utf8');
const appConfig = JSON.parse(fs.readFileSync(new URL('./app.json', import.meta.url), 'utf8'));

test('native push uses the EAS project identity and a real Expo push token', () => {
  assert.equal(appConfig.expo.extra.eas.projectId, 'c277466b-a418-45f7-b070-4fc3f96386b7');
  assert.match(notifications, /getExpoPushTokenAsync\(\{ projectId \}\)/);
  assert.match(notifications, /expoConfig\?\.extra\?\.eas\?\.projectId/);
});

test('morning delivery defaults to 08:00 local and is owned by the server', () => {
  assert.match(notifications, /const MORNING_HOUR = 8/);
  assert.match(notifications, /api\.setPushPreference\(\{ enabled: true, timezone, local_hour: MORNING_HOUR/);
  assert.match(notifications, /api\.registerPushDevice\(\{ token, platform: Platform\.OS, timezone \}\)/);
  assert.match(api, /setPushPreference:[\s\S]*\/push\/preference/);
  assert.match(api, /registerPushDevice:[\s\S]*\/push\/device/);
});

test('push token rotations are re-registered while the app is running', () => {
  assert.match(notifications, /addPushTokenListener/);
  assert.match(notifications, /PUSH_TOKEN_STORAGE_KEY/);
  assert.match(notifications, /api\.registerPushDevice/);
});

test('notification setting is mirrored to server without overwriting returning-user state on mount', () => {
  assert.match(storage, /mirrorNotificationPreference/);
  assert.match(storage, /syncPushPreference\(settings\.notifications\)/);
  assert.match(storage, /initialSettingsWritePending/);
  assert.match(storage, /if \(isDefaultSettings\(settings\)\) return/);
});

test('native signout revokes only this physical device before destroying session', () => {
  assert.match(supabase, /PUSH_TOKEN_STORAGE_KEY/);
  assert.match(supabase, /method: 'DELETE'/);
  assert.match(supabase, /body: JSON\.stringify\(\{ token: pushToken \}\)/);
  assert.match(supabase, /return originalSignOut/);
});

test('local alert polling is explicitly supplemental to closed-app server delivery', () => {
  assert.match(notifications, /morning digest is sent by[\s\S]*server/);
  assert.match(notifications, /syncUnreadOpportunityAlerts/);
});
