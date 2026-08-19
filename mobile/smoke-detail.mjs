import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');

const checks = [
  ['detail receives selected opportunity', /<Detail\s+initialItem=\{selected\}/],
  ['detail owns local opportunity state', /function Detail\(\{ initialItem,/],
  ['workflow is rendered in detail', /<WorkflowPanel item=\{item\}/],
  ['official source action is rendered', /Abrir fonte oficial/],
];

const crossFileChecks = [
  ['authenticated startup syncs alerts', /syncUnreadOpportunityAlerts/],
  ['foreground resumes alert sync', /AppState\.addEventListener\('change'/],
  ['notification sync reads unread server alerts', /api\.alerts\(\{ unreadOnly: true/],
  ['notification sync acknowledges delivered events', /api\.markAlertDelivered\(item\.event_id\)/],
  ['API exposes alerts endpoint', /alerts:\s*\(\{ limit = 20, unreadOnly = false \}/],
];

const failures = checks.filter(([, pattern]) => !pattern.test(app));
const crossFailures = [
  ...crossFileChecks.slice(0, 2).filter(([, pattern]) => !pattern.test(authGate)),
  ...crossFileChecks.slice(2, 4).filter(([, pattern]) => !pattern.test(notifications)),
  ...crossFileChecks.slice(4).filter(([, pattern]) => !pattern.test(api)),
];

if (failures.length || crossFailures.length) {
  for (const [name] of [...failures, ...crossFailures]) console.error(`FAIL: ${name}`);
  process.exit(1);
}

for (const [name] of [...checks, ...crossFileChecks]) console.log(`PASS: ${name}`);
