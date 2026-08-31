import fs from 'node:fs';
import { spawnSync } from 'node:child_process';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const authScreen = fs.readFileSync(new URL('./components/AuthScreen.tsx', import.meta.url), 'utf8');
const billingGate = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');
const billing = fs.readFileSync(new URL('./src/billing.js', import.meta.url), 'utf8');
const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const onboarding = fs.readFileSync(new URL('./components/ProfileOnboarding.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');
const storage = fs.readFileSync(new URL('./src/storage.js', import.meta.url), 'utf8');
const tenantStorage = fs.readFileSync(new URL('./src/tenantStorage.js', import.meta.url), 'utf8');

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

const failures = [
  ...checks.slice(0, 5).filter(([, pattern]) => !pattern.test(app)),
  ...checks.slice(5).filter(([, pattern]) => !pattern.test(onboarding)),
];
const crossFailures = [
  ...crossFileChecks.slice(0, 2).filter(([, pattern]) => !pattern.test(app)),
  ...crossFileChecks.slice(2, 4).filter(([, pattern]) => !pattern.test(notifications)),
  ...crossFileChecks.slice(4).filter(([, pattern]) => !pattern.test(api)),
];

if (failures.length || crossFailures.length) {
  for (const [name] of [...failures, ...crossFailures]) console.error(`FAIL: ${name}`);
  process.exit(1);
}

if (/api\.profile|syncUnreadOpportunityAlerts|AppState\.addEventListener/.test(authGate)) {
  console.error('FAIL: auth gate must not duplicate background API work');
  process.exit(1);
}

const privacyFailures = [];
if (!/nextState\.session\?\.user\?\.id/.test(authGate) || !/await storage\.bindPrivateTenant\(identity\)/.test(authGate)) privacyFailures.push('auth gate must bind Supabase identity before private shell');
if (!/signed-in' && !privateReady/.test(authGate)) privacyFailures.push('authenticated shell must wait for private storage binding');
if (!/privateStorage\.getSettings\(activePrivateTenant\)/.test(storage) || /AsyncStorage\.setItem\(KEYS\.settings/.test(storage)) privacyFailures.push('settings must be tenant-private');
if (!/envelope\.identity !== tenant/.test(tenantStorage) || !/@obrasignal\/v1\/settings/.test(tenantStorage)) privacyFailures.push('tenant storage must validate identity and purge legacy settings');
if (privacyFailures.length) {
  for (const name of privacyFailures) console.error(`FAIL: ${name}`);
  process.exit(1);
}

const tenantRegression = spawnSync(process.execPath, ['tenant-storage-regression.mjs'], { cwd: new URL('.', import.meta.url), encoding: 'utf8' });
if (tenantRegression.status !== 0) {
  console.error(tenantRegression.stdout);
  console.error(tenantRegression.stderr);
  console.error('FAIL: tenant storage dynamic regression');
  process.exit(1);
}

const uiFailures = [];
if (!/RADAR COMERCIAL/.test(app) || !/rootWide/.test(app)) uiFailures.push('authenticated workspace must use commercial shell');
if (/position:'absolute'/.test(billingGate)) uiFailures.push('billing status must never overlay authenticated content');
if (/A versão Web permite consultar o estado do plano, mas não processa compras/.test(billingGate)) uiFailures.push('web billing copy must not claim the platform cannot purchase');
if (!/EXPO_PUBLIC_REVENUECAT_WEB_KEY/.test(billing) || !/Platform\.OS === 'web'/.test(billing)) uiFailures.push('RevenueCat web billing configuration must be wired');
if (/flexBasis/.test(authScreen)) uiFailures.push('public landing must avoid flex-basis responsive overlap regression');
if (!/width >= 980/.test(authScreen) || !/heroStack/.test(authScreen)) uiFailures.push('public landing must have an explicit stacked breakpoint');
if (uiFailures.length) {
  for (const name of uiFailures) console.error(`FAIL: ${name}`);
  process.exit(1);
}

for (const [name] of [...checks, ...crossFileChecks]) console.log(`PASS: ${name}`);
for (const name of ['tenant-private authenticated storage','authenticated commercial shell','non-overlapping billing status','truthful web billing','responsive public landing']) console.log(`PASS: ${name}`);
