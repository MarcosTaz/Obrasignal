import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DEFAULT_LANGUAGE,PUBLIC_MARKET_LABEL,SUPPORTED_LANGUAGES,normalizeLanguage} from './ui-language.mjs';
import {EUROPE_MARKETS, EUROPE_COUNTRY_CODES} from './markets.js';

const file=path=>readFileSync(new URL(path,import.meta.url),'utf8');

test('English is the explicit default, independent of geolocation',()=>{
  assert.equal(DEFAULT_LANGUAGE,'en');
  assert.equal(normalizeLanguage(undefined),'en');
  assert.equal(normalizeLanguage('pt'),'en'); // PT is not advertised as fully translated yet.
  assert.deepEqual(SUPPORTED_LANGUAGES,['en']);
  assert.equal(PUBLIC_MARKET_LABEL,'International');
  const store=file('./storage.js');
  assert.match(store,/language: DEFAULT_LANGUAGE/);
  assert.match(store,/normalizeLanguage\(settings\?\.language\)/);
});
test('global brand messaging does not hard-code Portugal as presentation country',()=>{
  const landing=file('../components/AuthScreen.tsx');
  assert.doesNotMatch(landing,/Portugal|Portugal \+ Europa|instalações · Portugal/);
  assert.match(landing,/GLOBAL PROCUREMENT INTELLIGENCE/);
  assert.match(landing,/International outlook/);
  assert.match(landing,/Find opportunities worth pursuing/);
  assert.match(landing,/Request access/);
  assert.doesNotMatch(landing,/supabase\.auth\.signUp/);
});
test('new customer selects real supported markets instead of silently defaulting to Portugal',()=>{
  const onboarding=file('../components/ProfileOnboarding.js');
  assert.match(onboarding,/\?\s*'regions':'europe'/);
  assert.match(onboarding,/initialProfile\.countries:\[\]/);
  assert.match(onboarding,/Select at least one currently supported market/);
  assert.equal(EUROPE_COUNTRY_CODES.length,32);
  assert.equal(EUROPE_MARKETS.length,32);
  assert.deepEqual(EUROPE_COUNTRY_CODES.slice(0,3),['PRT','ESP','ITA']);
});
test('brand tagline and cinematic introduction are English',()=>{
  assert.match(file('../components/BrandLogo.js'),/PROCUREMENT INTELLIGENCE/);
  assert.match(file('../components/WebIntro.js'),/DISCOVER · EVALUATE · ACT/);
  assert.match(file('../App.web.js'),/Public procurement intelligence/);
  assert.match(file('../App.js'),/Public procurement intelligence/);
});
