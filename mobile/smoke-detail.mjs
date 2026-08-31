import fs from 'node:fs';

const app = fs.readFileSync(new URL('./App.js', import.meta.url), 'utf8');
const webApp = fs.readFileSync(new URL('./App.web.js', import.meta.url), 'utf8');
const authGate = fs.readFileSync(new URL('./components/AuthGate.js', import.meta.url), 'utf8');
const authScreen = fs.readFileSync(new URL('./components/AuthScreen.tsx', import.meta.url), 'utf8');
const billingGate = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');
const privacyControls = fs.readFileSync(new URL('./components/AccountPrivacyControls.js', import.meta.url), 'utf8');
const billing = fs.readFileSync(new URL('./src/billing.js', import.meta.url), 'utf8');
const notifications = fs.readFileSync(new URL('./src/notifications.js', import.meta.url), 'utf8');
const onboarding = fs.readFileSync(new URL('./components/ProfileOnboarding.js', import.meta.url), 'utf8');
const markets = fs.readFileSync(new URL('./src/markets.js', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('./src/api.js', import.meta.url), 'utf8');

const failures = [];
const requireMatch = (name, source, pattern) => { if (!pattern.test(source)) failures.push(name); };
const forbidMatch = (name, source, pattern) => { if (pattern.test(source)) failures.push(name); };

// Native/customer-detail fundamentals.
requireMatch('native detail receives selected opportunity', app, /<Detail\s+item=\{selected\}/);
requireMatch('native detail owns local opportunity state', app, /function Detail\(\{item,/);
requireMatch('native workflow action calls API', app, /api\.setWorkflow\(current\.id,next/);
requireMatch('native official-source action is rendered', app, /Abrir fonte oficial/);
requireMatch('native detail warns when official link is missing', app, /ligação à publicação oficial não está disponível/);
requireMatch('onboarding asks for business interests', onboarding, /Que trabalhos ou contratos procuras/);
requireMatch('CPV stays an advanced option', onboarding, /Opção avançada: rever códigos CPV/);
requireMatch('onboarding keeps canonical server profile after save', onboarding, /onComplete\(result\)/);
forbidMatch('onboarding must not discard server-derived profile fields', onboarding, /onComplete\(result\.profile\|\|draft\)/);

// Startup + notification wiring remains single-owner.
requireMatch('startup hydrates tenant cache before remote data', app, /Promise\.allSettled\(\[storage\.getSettings\(\),storage\.getCache\(\),storage\.getProfile\(\)\]\)/);
requireMatch('notification sync reads unread alerts', notifications, /api\.alerts\(\{ unreadOnly: true/);
requireMatch('notification sync acknowledges delivered events', notifications, /api\.markAlertDelivered\(item\.event_id\)/);
requireMatch('API exposes alerts endpoint', api, /alerts:\s*\(\{\s*limit\s*=\s*20,\s*unreadOnly\s*=\s*false\s*\}/);
forbidMatch('auth gate must not duplicate business API work', authGate, /api\.profile|syncUnreadOpportunityAlerts|AppState\.addEventListener/);

// Web must use the browser document as the vertical page rather than a nested RN viewport.
requireMatch('web document scroll hook exists', webApp, /function useDocumentScroll\(\)/);
requireMatch('web root explicitly allows vertical document scrolling', webApp, /overflowY='auto'/);
requireMatch('web root releases fixed height', webApp, /node\.style\.height='auto'/);
forbidMatch('web workspace must not trap Radar in FlatList', webApp, /FlatList/);
forbidMatch('web workspace must not use a top-level RN vertical ScrollView', webApp, /<ScrollView/);
requireMatch('web Radar cards remain normal-flow content', webApp, /visible\.map\(item=>/);
requireMatch('web detail retry must trigger a real reload', webApp, /onRetry=\{\(\)=>setReload\(value=>value\+1\)\}/);
forbidMatch('web detail must not expose a no-op retry', webApp, /onRetry=\{\(\)=>\{\}\}/);

// Complete Radar traversal + stable search criteria on both client surfaces.
requireMatch('API accepts offset', api, /offset=0/);
requireMatch('API sends offset query parameter', api, /offset:String\(offset\)/);
requireMatch('web retains server page metadata', webApp, /\[page,setPage\]/);
requireMatch('web load-more uses next_offset', webApp, /offset:page\.next_offset/);
requireMatch('web deduplicates appended opportunity ids', webApp, /const merged=new Map\(/);
requireMatch('web exposes load-more action', webApp, /Carregar mais oportunidades/);
requireMatch('web separates draft search from applied search', webApp, /\[appliedSearch,setAppliedSearch\]/);
requireMatch('native retains server page metadata', app, /\[page,setPage\]/);
requireMatch('native load-more uses next_offset', app, /offset:page\.next_offset/);
requireMatch('native deduplicates appended opportunity ids', app, /new Map\(\[\.\.\.current,\.\.\.fresh\]/);
requireMatch('native exposes load-more action', app, /Carregar mais oportunidades/);
requireMatch('native separates draft search from applied search', app, /\[appliedSearch,setAppliedSearch\]/);

// Session utilities are permanently reachable from the authenticated shell.
requireMatch('persistent web session bar contains logout', authGate, /Terminar sessão/);
requireMatch('persistent logout calls Supabase signOut', authGate, /supabase\.auth\.signOut\(\)/);
requireMatch('web session bar exposes on-demand translator', authGate, /function WebTranslator/);
requireMatch('translator is loaded only after activation', authGate, /if \(!enabled/);
requireMatch('translator sits in session controls', authGate, /<WebTranslator\/>/);
requireMatch('session clock uses 24-hour format', authGate, /hour12: false/);

// Privacy rights are available independently of paid/evaluation product access.
requireMatch('privacy controls wrap billing rather than sit inside it', authGate, /return <AccountPrivacyControls>[\s\S]*<BillingGate>/);
requireMatch('privacy export uses authenticated API', privacyControls, /api\.accountExport\(\)/);
requireMatch('privacy deletion uses exact destructive confirmation', privacyControls, /DELETE_MY_OBRASIGNAL_DATA/);
requireMatch('privacy deletion clears tenant-local private cache', privacyControls, /storage\.bindPrivateTenant\(null\)/);
requireMatch('privacy deletion attempts session signout', privacyControls, /supabase\.auth\.signOut\(\)/);
requireMatch('ambiguous deletion keeps private shell locked', privacyControls, /acesso privado permanece bloqueado/);
requireMatch('web export offers a JSON download', privacyControls, /Descarregar JSON/);
requireMatch('API client exposes account export', api, /accountExport:/);
requireMatch('API client exposes account deletion status', api, /accountDeletionStatus:/);
requireMatch('API client exposes account deletion write', api, /requestAccountDeletion:/);

// Billing access must be server-authoritative and fail closed.
requireMatch('billing requires server billing status', billingGate, /await api\.billingStatus\(\)/);
requireMatch('billing carries explicit server authority state', billingGate, /authority: 'loading'/);
requireMatch('pro access derives from server plan', billingGate, /pro: server\.plan === 'pro'/);
requireMatch('billing unavailable state blocks private access', billingGate, /Não foi possível validar o acesso/);
forbidMatch('billing must not overlay authenticated content', billingGate, /position:'absolute'/);
forbidMatch('web billing copy must not claim web purchases are impossible', billingGate, /A versão Web permite consultar o estado do plano, mas não processa compras/);
requireMatch('RevenueCat Web key remains wired', billing, /EXPO_PUBLIC_REVENUECAT_WEB_KEY/);

// Expired authentication recovery must work for protected writes too.
requireMatch('authenticated 401 refresh is one-shot', api, /response\.status===401 && !skipAuth && authRefreshes===0/);
forbidMatch('authenticated refresh must not be GET-only', api, /response\.status===401 && method==='GET'/);

// Branding + market coverage are consistent across public/authenticated/onboarding/native.
requireMatch('authenticated web uses refined ObraSignal wordmark', webApp, /Obra<Text style=\{s\.brandSignal\}>Signal/);
requireMatch('authenticated web uses shared font system', webApp, /fontFamily:FONT/);
requireMatch('public landing uses refined ObraSignal wordmark', authScreen, /Obra<Text style=\{styles\.brandAccent\}>Signal/);
requireMatch('onboarding uses refined ObraSignal wordmark', onboarding, /Obra<Text style=\{styles\.brandBlue\}>Signal/);
requireMatch('native shell uses refined ObraSignal wordmark', app, /Obra<Text style=\{s\.logoSignal\}>Signal/);
forbidMatch('public landing must not regress to all-caps prototype wordmark', authScreen, />OBRA<Text/);
forbidMatch('onboarding must not regress to all-caps prototype wordmark', onboarding, />OBRA<Text/);
const europeanMarketCount = (markets.match(/^\s*\['[A-Z]{3}',/gm) || []).length;
if (europeanMarketCount !== 32) failures.push(`European market registry must expose 32 markets, found ${europeanMarketCount}`);
requireMatch('web profile uses canonical Europe registry', webApp, /EUROPE_MARKETS\.map/);
requireMatch('native profile uses canonical Europe registry', app, /EUROPE_MARKETS\.map/);
requireMatch('onboarding uses canonical Europe registry', onboarding, /EUROPE_MARKETS\.map/);
if (!/32 mercados europeus (ativos|activos)/.test(webApp) || !/32 mercados europeus (ativos|activos)/.test(onboarding) || !/32 mercados europeus (ativos|activos)/.test(app)) failures.push('customer copy must state the active 32-market Europe scope');

// Public landing responsiveness + factual privacy disclosure.
forbidMatch('public landing must avoid flex-basis responsive overlap regression', authScreen, /flexBasis/);
requireMatch('public landing must have explicit wide breakpoint', authScreen, /width >= 980/);
requireMatch('public landing must have stacked compact hero', authScreen, /heroStack/);
requireMatch('public landing discloses authenticated data controls', authScreen, /exportação e pedido de eliminação dos dados privados/);

if (failures.length) {
  for (const name of failures) console.error(`FAIL: ${name}`);
  process.exit(1);
}

for (const name of [
  'native detail/workflow',
  'tenant startup + alerts',
  'browser document scrolling',
  'web detail retry',
  'Web + native Radar pagination',
  'persistent logout/date/time/translator',
  'account export + deletion ownership',
  'server-authoritative billing',
  'authenticated write token refresh',
  'consistent branding + 32-market registry',
  'responsive public landing',
]) console.log(`PASS: ${name}`);
