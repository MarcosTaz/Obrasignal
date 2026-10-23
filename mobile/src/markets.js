// Canonical client-side projection of VERIFIED European source coverage. Global brand strategy does not mean all countries are live.
// Keep this aligned with market_scope_registry.py: 9 dedicated BUILD markets
// plus 23 TED/eForms SHARED markets = 32 active European markets.
export const EUROPE_MARKETS = [
  ['PRT', 'Portugal'],
  ['ESP', 'Spain'],
  ['ITA', 'Italy'],
  ['FRA', 'France'],
  ['DEU', 'Germany'],
  ['CHE', 'Switzerland'],
  ['GBR', 'United Kingdom'],
  ['NLD', 'Netherlands'],
  ['POL', 'Poland'],
  ['AUT', 'Austria'],
  ['BEL', 'Belgium'],
  ['BGR', 'Bulgaria'],
  ['HRV', 'Croatia'],
  ['CYP', 'Cyprus'],
  ['CZE', 'Czechia'],
  ['DNK', 'Denmark'],
  ['EST', 'Estonia'],
  ['FIN', 'Finland'],
  ['GRC', 'Greece'],
  ['HUN', 'Hungary'],
  ['ISL', 'Iceland'],
  ['IRL', 'Ireland'],
  ['LVA', 'Latvia'],
  ['LIE', 'Liechtenstein'],
  ['LTU', 'Lithuania'],
  ['LUX', 'Luxembourg'],
  ['MLT', 'Malta'],
  ['NOR', 'Norway'],
  ['ROU', 'Romania'],
  ['SVK', 'Slovakia'],
  ['SVN', 'Slovenia'],
  ['SWE', 'Sweden'],
];

export const EUROPE_COUNTRY_CODES = EUROPE_MARKETS.map(([code]) => code);
