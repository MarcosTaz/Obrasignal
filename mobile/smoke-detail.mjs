import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
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
  ['startup hydrates local cache before remote data', /Promise\.all\(\[storage\.getSettings\(\),storage\.getCache\(\),storage\.getProfile\(\)\]\)/],
  ['startup loads independent API data concurrently', /Promise\.allSettled\(\[api\.opportunities/],
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

for (const [name] of [...checks, ...crossFileChecks]) console.log(`PASS: ${name}`);
