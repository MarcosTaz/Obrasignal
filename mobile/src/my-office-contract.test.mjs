import test from 'node:test';
import assert from 'node:assert/strict';
import {MY_OFFICE_ENABLED, MODULES, SUPPORTED_LANGUAGES, languageOf, moduleFor, routeFor, translate} from './my-office-contract.mjs';

test('safe by default: not activated until visual and E2E sign-off', () => {
  assert.equal(MY_OFFICE_ENABLED,false);
});
test('exactly seven unambiguous functional areas', () => {
  assert.equal(MODULES.length,7);
  assert.equal(new Set(MODULES.map(m=>m.id)).size,7);
});
test('only canonical existing routes can be opened', () => {
  assert.equal(routeFor('radar'),'radar');
  assert.equal(routeFor('profile'),'profile');
  for(const m of MODULES.filter(m=>m.status!=='existing')) assert.equal(routeFor(m.id),null);
  assert.equal(routeFor('__missing__'),null);
  assert.equal(moduleFor('__missing__'),null);
});
test('five supported locales and explicit fallback', () => {
  assert.deepEqual(SUPPORTED_LANGUAGES,['pt','en','es','fr','de']);
  for(const lang of SUPPORTED_LANGUAGES)
    for(const m of MODULES) assert.notEqual(translate(lang,m.id),m.id);
  assert.equal(languageOf('en-US'),'en');
  assert.equal(languageOf('zz'),'pt');
  assert.equal(translate('zz','radar'),'Radar de concursos');
});
