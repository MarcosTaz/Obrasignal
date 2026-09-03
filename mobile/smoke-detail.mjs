import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const authScreen = fs.readFileSync(new URL('./components/AuthScreen.tsx', import.meta.url), 'utf8');
const sessionCoordinator = fs.readFileSync(new URL('./src/sessionCoordinator.js', import.meta.url), 'utf8');
const billingGate = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');
const billing = fs.readFileSync(new URL('./src/billing.js', import.meta.url), 'utf8');
const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const onboarding = fs.readFileSync(new URL('./components/ProfileOnboarding.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');
const storage = fs.readFileSync(new URL('./src/storage.js', import.meta.url), 'utf8');

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
  ['startup hydrates local cache before remote data', /Promise\.allSettled\(\[storage\.getSettings\(\),storage\.getCache\(\),storage\.getProfile\(\)\]\)/, app],
  ['startup loads independent API data concurrently', /Promise\.allSettled\(\[api\.profile\(\),api\.opportunities/, app],
  ['notification sync reads unread server alerts', /api\.alerts\(\{ unreadOnly: true/, notifications],
  ['notification sync acknowledges delivered events', /api\.markAlertDelivered\(item\.event_id\)/, notifications],
  ['API exposes alerts endpoint', /alerts:\s*\(\{\s*limit\s*=\s*20,\s*unreadOnly\s*=\s*false\s*\}/, api],
  ['auth gate scopes local state before publishing signed-in state', /storage\.setAccountScope\(accountScopeFor\(nextState\)\)[\s\S]*setAuthState\(nextState\)/, authGate],
  ['signed-out and recovery states have no local account scope', /return state\?\.status === 'signed-in' \? state\?\.session\?\.user\?\.id \|\| null : null/, authGate],
  ['password recovery event becomes distinct non-product state', /event === 'PASSWORD_RECOVERY'[\s\S]*'password-recovery'/, sessionCoordinator],
  ['recovery session cannot mint backend authorization header', /if \(state\.status === 'password-recovery'\) return null/, sessionCoordinator],
  ['auth gate intercepts recovery before billing/product shell', /if \(authState\.status === 'password-recovery'\)[\s\S]*<AuthScreen recoverySession=\{authState\.session\}/, authGate],
  ['forgot password requests provider recovery email', /supabase\.auth\.resetPasswordForEmail\(/, authScreen],
  ['recovery updates password through provider authority', /supabase\.auth\.updateUser\(\{ password \}\)/, authScreen],
  ['recovery ends with sign-out before fresh sign-in', /updateUser\(\{ password \}\)[\s\S]*supabase\.auth\.signOut\(\)[\s\S]*setMode\('signIn'\)/, authScreen],
  ['customer cache/profile/settings derive account-scoped keys', /function scopedStorageKey\(baseKey, accountId = activeAccountScope\)[\s\S]*encodeURIComponent\(scope\)/, storage],
  ['storage rejects writes without authenticated account scope', /Promise\.reject\(new Error\('account_scope_required'\)\)/, storage],
  ['storage rechecks scope after asynchronous read', /return activeAccountScope === scope \? value : fallback/, storage],
  ['expired billing gate still exposes sign-out/account-switch action', /A avaliação terminou[\s\S]*onPress=\{signOut\}[\s\S]*Terminar sessão ou trocar de conta/, billingGate],
  ['expired billing sign-out uses canonical Supabase auth', /const signOut = async \(\) => \{[\s\S]*supabase\.auth\.signOut\(\)/, billingGate],
  ['web billing remains the same pro entitlement owner', /BILLING_ENTITLEMENT = 'pro'[\s\S]*BILLING_PRODUCT = 'obrasignal_pro_monthly'/, billing],
  ['web purchase link is runtime configured not hard coded', /EXPO_PUBLIC_REVENUECAT_WEB_PURCHASE_URL/, billing],
  ['web purchase requires identified app user id in URL path', /new URL\(`\$\{base\}\/\$\{encodeURIComponent\(userId\)\}`\)/, billing],
  ['web purchase opens only through validated HTTPS URL', /parsed\.protocol !== 'https:'[\s\S]*Linking\.canOpenURL\(url\)[\s\S]*Linking\.openURL\(url\)/, billing],
  ['web paywall uses authenticated Supabase subject', /openWebPurchase\(session\.user\.id, session\.user\.email \|\| null\)/, billingGate],
  ['web checkout does not locally grant entitlement', /The hosted checkout is authoritative[\s\S]*new app load\/refresh reads server truth/, billingGate],
];

const failures = [
  ...checks.slice(0, 5).filter(([, pattern]) => !pattern.test(app)),
  ...checks.slice(5).filter(([, pattern]) => !pattern.test(onboarding)),
];
const crossFailures = crossFileChecks.filter(([, pattern, source]) => !pattern.test(source));

if (failures.length || crossFailures.length) {
  for (const [name] of [...failures, ...crossFailures]) console.error(`FAIL: ${name}`);
  process.exit(1);
}

if (/api\.profile|syncUnreadOpportunityAlerts|AppState\.addEventListener/.test(authGate)) {
  console.error('FAIL: auth gate must not duplicate background API work');
  process.exit(1);
}

if (/readJson\(KEYS\.(profile|cache|saved|settings)/.test(storage)) {
  console.error('FAIL: user-scoped customer data must not read legacy unscoped keys');
  process.exit(1);
}

for (const [name] of [...checks, ...crossFileChecks]) console.log(`PASS: ${name}`);
