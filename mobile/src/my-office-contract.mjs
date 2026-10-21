// ObraSignal My Office bridge — opt-in integration, no demo authentication or fake tenders.
// This feature is intentionally gated until visual fidelity and E2E validation are complete.
// This opt-in is compiled into the web bundle only when deliberately enabled.
// Default deployments remain disabled until approved original assets and E2E pass.
export const MY_OFFICE_ENABLED = process.env.EXPO_PUBLIC_MY_OFFICE_ENABLED === 'true';

export const MODULES = Object.freeze([
  { id: 'radar', target: 'radar', status: 'existing' },
  { id: 'dossiers', target: null, status: 'not-integrated' },
  { id: 'profile', target: 'profile', status: 'existing' },
  { id: 'portfolio', target: null, status: 'not-integrated' },
  { id: 'export', target: null, status: 'not-integrated' },
  { id: 'context', target: null, status: 'not-integrated' },
  { id: 'next', target: null, status: 'not-integrated' },
]);

const STRINGS = Object.freeze({
  'pt': { office:'My Office', radar:'Radar de concursos', dossiers:'Dossiês e prova', profile:'Empresa e perfil', portfolio:'Portefólio', export:'Exportar dados', context:'Contexto', next:'Próxima ação', pending:'Integração pendente', open:'Abrir área' },
  'en': { office:'My Office', radar:'Tender radar', dossiers:'Dossiers and evidence', profile:'Company and profile', portfolio:'Portfolio', export:'Export data', context:'Context', next:'Next action', pending:'Integration pending', open:'Open area' },
  'es': { office:'My Office', radar:'Radar de licitaciones', dossiers:'Expedientes y pruebas', profile:'Empresa y perfil', portfolio:'Cartera', export:'Exportar datos', context:'Contexto', next:'Siguiente acción', pending:'Integración pendiente', open:'Abrir área' },
  'fr': { office:'My Office', radar:'Radar des appels d’offres', dossiers:'Dossiers et preuves', profile:'Entreprise et profil', portfolio:'Portefeuille', export:'Exporter les données', context:'Contexte', next:'Prochaine action', pending:'Intégration en attente', open:'Ouvrir la section' },
  'de': { office:'My Office', radar:'Ausschreibungsradar', dossiers:'Dossiers und Nachweise', profile:'Unternehmen und Profil', portfolio:'Portfolio', export:'Daten exportieren', context:'Kontext', next:'Nächster Schritt', pending:'Integration ausstehend', open:'Bereich öffnen' },
});

export const SUPPORTED_LANGUAGES = Object.freeze(Object.keys(STRINGS));
export function languageOf(locale) {
  const normalized = String(locale || 'pt').toLowerCase().split(/[-_]/)[0];
  return Object.prototype.hasOwnProperty.call(STRINGS, normalized) ? normalized : 'pt';
}
export function translate(locale, key) {
  const language = languageOf(locale);
  return STRINGS[language][key] || STRINGS.pt[key] || key;
}
export function moduleFor(id) { return MODULES.find(item => item.id === id) || null; }
export function routeFor(id) {
  const module = moduleFor(id);
  // Never route an unimplemented module to a made-up page.
  return module && module.status === 'existing' ? module.target : null;
}
