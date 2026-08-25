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
  ['workflow is rendered in detail', /const status=current\.workflow\?\.status\|\|'NEW'/],
  ['workflow action calls API', /api\.setWorkflow\(current\.id,next/],
  ['official source action is rendered', /Abrir fonte oficial/],
  ['onboarding asks for business interests', /Que trabalhos ou contratos procuras/],
  ['CPV is an advanced option', /Opção avançada: rever códigos CPV/],
  ['internal economic fit is absent from onboarding', /Economic Fit/.test(onboarding) ? /$a/ : /contract_interests/],
];

const crossFileChecks = [
  ['startup hydrates local cache before remote data', /Promise\.allSettled\(\[storage\.getSettings\(\),storage\.getCache\(\),storage\.getProfile\(\)\]\)/],
  ['startup loads independent API data concurrently', /Promise\.allSettled\(\[api\.profile\(\),api\.opportunities/],
  ['notification sync reads unread server alerts', /api\.alerts\(\{ unreadOnly: true/],
  ['notification sync acknowledges delivered events', /api\.markAlertDelivered\(item\.event_id\)/],
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
  ['notification tap validates tenant-private binding before navigation', notifications, /current\.bindingId !== bindingId/],
  ['cold-start notification response is consumed', notifications, /getLastNotificationResponseAsync\(\)/],
  ['live notification response listener is installed', notifications, /addNotificationResponseReceivedListener\(handle\)/],
  ['tap return fetches current opportunity truth before opening detail', app, /openNotificationOpportunity[\s\S]*api\.opportunity\(opportunityId\)/],
  ['unavailable tapped opportunity fails honestly', app, /notificação já não está disponível/],
  ['tap return refreshes current Radar truth', app, /loadRef\.current\?\.\(\{preserve:true\}\)/],
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

for (const [name] of [...checks, ...crossFileChecks, ...authIsolationChecks, ...pushChecks]) console.log(`PASS: ${name}`);
