import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const webApp = fs.readFileSync(new URL('./App.web.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const authScreen = fs.readFileSync(new URL('./components/AuthScreen.tsx', import.meta.url), 'utf8');
const billingGate = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');
const billing = fs.readFileSync(new URL('./src/billing.js', import.meta.url), 'utf8');
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

const uiFailures = [];
if (!/RADAR COMERCIAL/.test(app) || !/rootWide/.test(app)) uiFailures.push('authenticated workspace must use commercial shell');
if (/position:'absolute'/.test(billingGate)) uiFailures.push('billing status must never overlay authenticated content');
if (/A versão Web permite consultar o estado do plano, mas não processa compras/.test(billingGate)) uiFailures.push('web billing copy must not claim the platform cannot purchase');
if (!/EXPO_PUBLIC_REVENUECAT_WEB_KEY/.test(billing) || !/Platform\.OS === 'web'/.test(billing)) uiFailures.push('RevenueCat web billing configuration must be wired');
if (/flexBasis/.test(authScreen)) uiFailures.push('public landing must avoid flex-basis responsive overlap regression');
if (!/width >= 980/.test(authScreen) || !/heroStack/.test(authScreen)) uiFailures.push('public landing must have an explicit stacked breakpoint');
if (!/function WebMain/.test(webApp) || !/<ScrollView style=\{s\.pageScroll\}/.test(webApp)) uiFailures.push('web workspace must have one explicit vertical scroll surface');
if (/FlatList/.test(webApp)) uiFailures.push('web workspace must not trap the Radar in a nested FlatList scroll viewport');
if (!/visible\.map\(item=>/.test(webApp)) uiFailures.push('web Radar cards must participate in the page scroll flow');
if (!/Obra<Text style=\{s\.brandSignal\}>Signal/.test(webApp) || !/fontFamily:FONT/.test(webApp)) uiFailures.push('web brand typography must use the refined wordmark system');
if (/Terminar sessão/.test(authGate)) uiFailures.push('web session header must not advertise logout');
if (!/Terminar sessão/.test(webApp) || !/style=\{s\.signOut\}/.test(webApp)) uiFailures.push('logout must remain available discreetly at the bottom of the profile');
if (!/Intl\.DateTimeFormat\('pt-PT'/.test(authGate) || !/second:\s*'2-digit'/.test(authGate)) uiFailures.push('web session header must keep Portuguese date and live clock');
if (uiFailures.length) {
  for (const name of uiFailures) console.error(`FAIL: ${name}`);
  process.exit(1);
}

for (const [name] of [...checks, ...crossFileChecks]) console.log(`PASS: ${name}`);
for (const name of ['authenticated commercial shell','non-overlapping billing status','truthful web billing','responsive public landing','single web page scroll','refined web wordmark','discreet profile logout','web date and clock']) console.log(`PASS: ${name}`);
