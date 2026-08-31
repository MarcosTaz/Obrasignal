import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const storageSource = fs.readFileSync(new URL('./src/storage.js', import.meta.url), 'utf8');
const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const onboarding = fs.readFileSync(new URL('./components/ProfileOnboarding.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');

const checks = [
  ['detail receives selected opportunity', /<Detail\s+item=\{selected\}/],
  ['detail owns local opportunity state', /function Detail\(\{item,/],
  ['workflow is rendered in detail without fabricated default', /const status=current\.workflow\?\.status\?\?null;const statusKnown=workflowStatusKnown\(status\)/],
  ['workflow action calls API', /api\.setWorkflow\(current\.id,next/],
  ['official source action is rendered', /Abrir fonte oficial/],
  ['onboarding asks for business interests', /Que trabalhos ou contratos procuras/],
  ['CPV is an advanced option', /Opção avançada: rever códigos CPV/],
  ['internal economic fit is absent from onboarding', /Economic Fit/.test(onboarding) ? /$a/ : /contract_interests/],
];

const crossFileChecks = [
  ['startup hydrates local cache before remote data', /Promise\.allSettled\(\[storage\.getSettings\(\),storage\.getCache\(\),storage\.getProfile\(\)\]\)/],
  ['startup loads independent API data concurrently', /Promise\.allSettled\(\[append\?Promise\.resolve\(profile\):api\.profile\(\),api\.opportunities/],
  ['notification sync reads unread server alerts', /api\.alerts\(\{ unreadOnly: true/],
  ['notification sync records scheduling without delivered completion', /rememberLocalScheduledEvent\(eventId\)/],
  ['API exposes alerts endpoint', /alerts:\s*\(\{\s*limit\s*=\s*20,\s*unreadOnly\s*=\s*false\s*\}/],
];

const authIsolationChecks = [
  ['auth gate blocks authenticated shell until private tenant binding completes', authGate, /setTenantStatus\('loading'\)[\s\S]*await storage\.bindPrivateTenant\(accountId\)[\s\S]*setTenantStatus\('ready'\)/],
  ['authenticated subtree remounts when session identity changes', authGate, /<BillingGate key=\{accountId\}>\{children\}<\/BillingGate>/],
  ['private storage facade clears the active identity before asynchronous rebind', storageSource, /activePrivateTenant = null;[\s\S]*await privateStorage\.bindTenant\(accountId\)/],
  ['unbound Radar cache reads fail closed', storageSource, /getCache: \(\) => activePrivateTenant \? privateStorage\.getCache\(activePrivateTenant\) : Promise\.resolve\(null\)/],
  ['unbound profile cache reads fail closed', storageSource, /getProfile: \(\) => activePrivateTenant \? privateStorage\.getProfile\(activePrivateTenant\) : Promise\.resolve\(null\)/],
];

const pushChecks = [
  ['native client obtains an Expo push token for the canonical EAS project', notifications, /getExpoPushTokenAsync\(\{ projectId: EXPO_PROJECT_ID \}\)/],
  ['push token is registered through the authenticated API facade', notifications, /api\.registerPushDevice\(\{ installationId, expoPushToken, platform: Platform\.OS \}\)/],
  ['permission denial remains distinct from zero local schedules', notifications, /return \{ status: 'permission_denied', scheduled: 0 \}/],
  ['permission denial has truthful customer copy', app, /Notificações não ativadas: permissão recusada no dispositivo/],
  ['remote registration does not claim background delivery', app, /Dispositivo registado para notificações remotas\. A entrega em segundo plano ainda não está comprovada neste build\./],
  ['unregister revokes local binding before the bounded server attempt', notifications, /storage\.clearPushBinding\(\)[\s\S]*api\.unregisterPushDevice\(binding\.installationId\)/],
  ['disabled notifications fail closed before tap binding validation', notifications, /getSettings\(\)[\s\S]*if \(!settings\.notifications\) return null;[\s\S]*getPushBinding\(\)/],
  ['storage facade exposes tenant-private binding revoke', storageSource, /clearPushBinding: \(\) => activePrivateTenant \? privateStorage\.clearPushBinding\(activePrivateTenant\) : Promise\.resolve\(\)/],
  ['storage facade exposes tenant-private scheduled evidence', storageSource, /getLocalNotificationScheduled:[\s\S]*setLocalNotificationScheduled:/],
  ['local fallback creates tenant-private tap authority before scheduling', notifications, /binding = \{ bindingId: newLocalBindingId\(\), kind: 'local' \};[\s\S]*storage\.setPushBinding\(binding\)/],
  ['local notification payload never falls back to a null binding', notifications, /bindingId: binding\.bindingId/],
  ['local fallback tray remains tenant-neutral', notifications, /body: 'Abre o ObraSignal para confirmar uma nova oportunidade\.'/],
  ['missing current binding dismisses stale tray before provider token attempt', notifications, /if \(!existingBinding\)[\s\S]*dismissAllNotificationsAsync\(\)[\s\S]*getExpoPushTokenAsync\(\{ projectId: EXPO_PROJECT_ID \}\)/],
  ['local-only authority is dismissed only after remote binding succeeds', notifications, /const bindingId = String\(response\?\.binding_id[\s\S]*if \(existingBinding && !isRemoteBinding\(existingBinding\)\)[\s\S]*dismissAllNotificationsAsync\(\)[\s\S]*storage\.setPushBinding\(\{ bindingId, installationId, expoPushToken, kind: 'remote' \}\)/],
  ['notification tap validates tenant-private binding before navigation', notifications, /current\.bindingId !== bindingId/],
  ['notification response marks delivered only after tap authority validation', notifications, /current\.bindingId !== bindingId[\s\S]*api\.markAlertDelivered\(eventId\)/],
  ['notification response id is claimed before async target validation', notifications, /handledResponseIds\.add\(responseId\)[\s\S]*await notificationOpportunityTarget\(response\)/],
  ['cold-start notification response is consumed', notifications, /getLastNotificationResponseAsync\(\)/],
  ['consumed native response is cleared to prevent later replay', notifications, /clearLastNotificationResponseAsync\(\)/],
  ['live notification response listener is installed', notifications, /addNotificationResponseReceivedListener\(handle\)/],
  ['tap return fetches current opportunity truth before opening detail', app, /openNotificationOpportunity[\s\S]*api\.opportunity\(opportunityId\)/],
  ['closed or non-actionable tapped opportunity returns to current Radar', app, /fresh\?\.is_actionable===false\|\|fresh\?\.deadline_status\?\.state==='closed'[\s\S]*já não está acionável[\s\S]*loadRef\.current\?\.\(\{manual:true,offset:0\}\)/],
  ['unavailable tapped opportunity fails honestly', app, /notificação já não está disponível/],
  ['tap return refreshes current Radar truth', app, /loadRef\.current\?\.\(\{preserve:true,offset:0\}\)/],
  ['sign-out attempts server unregister before Supabase sign-out', app, /unregisterRemoteOpportunityPush\(\)[\s\S]*supabase\.auth\.signOut\(\)/],
  ['API facade exposes push registration', api, /registerPushDevice:\(\{installationId,expoPushToken,platform\}\)/],
  ['API facade exposes push unregister', api, /unregisterPushDevice:\(installationId\)/],
  ['push binding is unavailable while private storage is unbound', storageSource, /getPushBinding: \(\) => activePrivateTenant \? privateStorage\.getPushBinding\(activePrivateTenant\) : Promise\.resolve\(null\)/],
];

const failures = [
  ...checks.slice(0, 5).filter(([, pattern]) => !pattern.test(app)),
  ...checks.slice(5).filter(([, pattern]) => !pattern.test(onboarding)),
];
const crossFailures = [
  ...crossFileChecks.slice(0, 2).filter(([, pattern]) => !pattern.test(app)),
  ...crossFileChecks.slice(2, 4).filter(([, pattern]) => !pattern.test(notifications)),
  ...crossFileChecks.slice(4).filter(([, pattern]) => !pattern.test(api)),
];
const authIsolationFailures = authIsolationChecks.filter(([, source, pattern]) => !pattern.test(source));
const pushFailures = pushChecks.filter(([, source, pattern]) => !pattern.test(source));

if (failures.length || crossFailures.length || authIsolationFailures.length || pushFailures.length) {
  for (const [name] of [...failures, ...crossFailures, ...authIsolationFailures, ...pushFailures]) console.error(`FAIL: ${name}`);
  process.exit(1);
}

if (/api\.profile|syncUnreadOpportunityAlerts|AppState\.addEventListener/.test(authGate)) {
  console.error('FAIL: auth gate must not duplicate background API work');
  process.exit(1);
}

if (/Notificações push activadas\./.test(app)) {
  console.error('FAIL: token registration must not be presented as proven background push delivery');
  process.exit(1);
}

if (/body:\s*item\?\.title/.test(notifications)) {
  console.error('FAIL: local notification tray must not expose tenant-specific opportunity title');
  process.exit(1);
}

if (/if \(!isRemoteBinding\(existingBinding\)\)[\s\S]*getExpoPushTokenAsync/.test(notifications)) {
  console.error('FAIL: local fallback alerts must survive a failed remote registration attempt');
  process.exit(1);
}

for (const [name] of [...checks, ...crossFileChecks, ...authIsolationChecks, ...pushChecks]) console.log(`PASS: ${name}`);