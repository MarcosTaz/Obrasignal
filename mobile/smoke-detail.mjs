import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const onboarding = fs.readFileSync(new URL('./components/ProfileOnboarding.js', import.meta.url), 'utf8');
const opportunityExplanation = fs.readFileSync(new URL('./components/OpportunityExplanation.js', import.meta.url), 'utf8');
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
  ['notification contract exposes permission denial', /status: 'permission_denied'/],
  ['notification contract exposes unsupported web', /status: 'unsupported'/],
  ['API exposes alerts endpoint', /alerts:\s*\(\{\s*limit\s*=\s*20,\s*unreadOnly\s*=\s*false\s*\}/],
];

const truthChecks = [
  ['unknown stats have an explicit renderer', /metricText\(v\)/],
  ['cached stats are disclosed as stale', /Contagens guardadas; a atualização não pôde ser confirmada\./],
  ['missing stats failure is disclosed unavailable', /Contagens temporariamente indisponíveis\./],
  ['stats state distinguishes stale from unavailable', /setStatsState\(hasStats\(freshStats\)\?'stale':'unavailable'\)/],
  ['cached stats start stale until server verification', /setStatsState\(hasStats\(cachedStats\)\?'stale':'loading'\)/],
  ['unknown score has an explicit renderer', /scoreText\(score\)/],
  ['missing source has an explicit renderer', /sourceText\(item\.source\)/],
  ['score is framed as compatibility, not a bid recommendation', /A pontuação expressa compatibilidade com o perfil; não é uma recomendação para concorrer\./],
  ['web notifications are disclosed as unavailable', /Notificações do navegador ainda não estão disponíveis\./],
  ['web notification switch is disabled', /<Switch disabled=\{webNotifications\} value=\{webNotifications\?false:/],
];

const explanationTruthChecks = [
  ['factor rendering is neutral unless semantics are explicit', /visibleFactors\.map\(\(factor\) => <Factor key=\{factor\.key\} title=\{factor\.label\} text=\{factor\.reason\} score=\{factor\.score\} \/>\)/],
];

const forbiddenTruthPatterns = [
  ['stats must not default UNKNOWN to zero', /\{v\?\?0\}/],
  ['card score must not default UNKNOWN to zero', /item\.decision_score\?\?item\.score\?\?0/],
  ['detail score must not default UNKNOWN to zero', /current\.decision_score\?\?current\.score\?\?0/],
  ['card source must not fabricate TED', /item\.source\|\|'TED'/],
  ['detail source must not fabricate TED', /current\.source\|\|'TED'/],
  ['score must not be described as a recommendation', /O scoring é uma recomendação/],
  ['notification denial must not collapse to activated copy', /Notificações activadas\./],
];

const forbiddenExplanationPatterns = [
  ['factor type must not manufacture a positive visual signal', /toneForFactor/],
];

const failures = [
  ...checks.slice(0, 5).filter(([, pattern]) => !pattern.test(app)),
  ...checks.slice(5).filter(([, pattern]) => !pattern.test(onboarding)),
  ...truthChecks.filter(([, pattern]) => !pattern.test(app)),
  ...explanationTruthChecks.filter(([, pattern]) => !pattern.test(opportunityExplanation)),
  ...forbiddenTruthPatterns.filter(([, pattern]) => pattern.test(app)),
  ...forbiddenExplanationPatterns.filter(([, pattern]) => pattern.test(opportunityExplanation)),
];
const crossFailures = [
  ...crossFileChecks.slice(0, 2).filter(([, pattern]) => !pattern.test(app)),
  ...crossFileChecks.slice(2, 6).filter(([, pattern]) => !pattern.test(notifications)),
  ...crossFileChecks.slice(6).filter(([, pattern]) => !pattern.test(api)),
];

if (failures.length || crossFailures.length) {
  for (const [name] of [...failures, ...crossFailures]) console.error(`FAIL: ${name}`);
  process.exit(1);
}

if (/api\.profile|syncUnreadOpportunityAlerts|AppState\.addEventListener/.test(authGate)) {
  console.error('FAIL: auth gate must not duplicate background API work');
  process.exit(1);
}

for (const [name] of [...checks, ...crossFileChecks, ...truthChecks, ...explanationTruthChecks]) console.log(`PASS: ${name}`);
