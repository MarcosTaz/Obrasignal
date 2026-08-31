// Canonical client-side projection of the active European product scope.
// Keep this aligned with market_scope_registry.py: 9 dedicated BUILD markets
// plus 23 TED/eForms SHARED markets = 32 active European markets.
export const EUROPE_MARKETS = [
  ['PRT', 'Portugal'],
  ['ESP', 'Espanha'],
  ['ITA', 'Itália'],
  ['FRA', 'França'],
  ['DEU', 'Alemanha'],
  ['CHE', 'Suíça'],
  ['GBR', 'Reino Unido'],
  ['NLD', 'Países Baixos'],
  ['POL', 'Polónia'],
  ['AUT', 'Áustria'],
  ['BEL', 'Bélgica'],
  ['BGR', 'Bulgária'],
  ['HRV', 'Croácia'],
  ['CYP', 'Chipre'],
  ['CZE', 'Chéquia'],
  ['DNK', 'Dinamarca'],
  ['EST', 'Estónia'],
  ['FIN', 'Finlândia'],
  ['GRC', 'Grécia'],
  ['HUN', 'Hungria'],
  ['ISL', 'Islândia'],
  ['IRL', 'Irlanda'],
  ['LVA', 'Letónia'],
  ['LIE', 'Liechtenstein'],
  ['LTU', 'Lituânia'],
  ['LUX', 'Luxemburgo'],
  ['MLT', 'Malta'],
  ['NOR', 'Noruega'],
  ['ROU', 'Roménia'],
  ['SVK', 'Eslováquia'],
  ['SVN', 'Eslovénia'],
  ['SWE', 'Suécia'],
];

export const EUROPE_COUNTRY_CODES = EUROPE_MARKETS.map(([code]) => code);
