import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { BRAND_MARK_PATHS, buildBrandMarkSvg, brandMarkDataUri } from './logo-geometry.mjs';
import { BRAND } from './brand-palette.mjs';
test('approved corporate mark has five closed master paths',()=>{
  assert.equal(Object.keys(BRAND_MARK_PATHS).length,5);
  for(const p of Object.values(BRAND_MARK_PATHS)) {
    assert.match(p,/^M\d+ /);
    assert.match(p,/Z$/);
  }
});
test('public SVG derivatives use exact master paths and immutable approved colours',()=>{
  const mark=readFileSync(new URL('../public/obrasignal-monogram.svg',import.meta.url),'utf8');
  const wordmark=readFileSync(new URL('../public/obrasignal-logo.svg',import.meta.url),'utf8');
  for(const p of Object.values(BRAND_MARK_PATHS)){
    assert.ok(mark.includes(p),'monogram master path missing: '+p);
    assert.ok(wordmark.includes(p),'lockup master path missing: '+p);
  }
  for(const color of [BRAND.slate,BRAND.mineral,BRAND.copper]){
    assert.ok(mark.includes(color));
    assert.ok(wordmark.includes(color));
  }
  assert.match(wordmark,/Obra/);
  assert.match(wordmark,/Signal/);
});
test('favicon uses transparent-or-paper SVG and is consistent with master geometry',()=>{
  const svg=buildBrandMarkSvg({background:BRAND.paper});
  assert.match(svg,/viewBox="0 0 116 120"/);
  assert.match(svg,/fill="#C87D55"/);
  assert.ok(brandMarkDataUri.startsWith('data:image/svg+xml,'));
  assert.ok(decodeURIComponent(brandMarkDataUri.split(',')[1]).includes(BRAND_MARK_PATHS.decision));
});
test('brand is theme invariant and has no DOM mutations to coloured wordmark',()=>{
  const component=readFileSync(new URL('../components/BrandLogo.js',import.meta.url),'utf8');
  const web=readFileSync(new URL('./webBranding.js',import.meta.url),'utf8');
  assert.doesNotMatch(component,/createThemeColors|settings\.theme/);
  assert.doesNotMatch(web,/MutationObserver|decorateWordmarks|ELECTRIC_BLUE/);
  assert.match(component,/BRAND_MARK_PATHS/);
  assert.match(component,/accessible accessibilityLabel="ObraSignal"/);
});
