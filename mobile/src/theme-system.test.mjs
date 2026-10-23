import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_THEME,THEMES,resolveTheme,createThemeColors} from './theme-system.mjs';
import {BRAND} from './brand-palette.mjs';
import {readFileSync} from 'node:fs';

function luminance(hex) {
  const rgb=hex.match(/[0-9a-f]{2}/gi).map(bit=>parseInt(bit,16)/255);
  return rgb.reduce((total,n,index)=>total+[.2126,.7152,.0722][index]*(n<=.04045?n/12.92:((n+.055)/1.055)**2.4),0);
}
function contrast(a,b){const la=luminance(a),lb=luminance(b);return (Math.max(la,lb)+.05)/(Math.min(la,lb)+.05);}
test('default identity is explicit and not the old midnight palette',()=>{
  assert.equal(DEFAULT_THEME,'signature');
  assert.notEqual(createThemeColors(DEFAULT_THEME).bg,'#07111C');
});
test('all user-submitted palette choices are available without duplication',()=>{
  const expected=['signature','glass-graphite','warm-linen','sage','modern-moss','minimal-beige','slate-circuit','steel-lavender','midnight-blue','original-night'];
  assert.deepEqual(THEMES.map(t=>t.id),expected);
});
test('theme fallback does not trust a persisted unknown identifier',()=>{
  assert.equal(resolveTheme('invalid').id,DEFAULT_THEME);
  assert.equal(resolveTheme(null).id,DEFAULT_THEME);
});
test('all themes produce valid five-color swatches and design tokens',()=>{
  for(const theme of THEMES){
    assert.equal(theme.swatches.length,5);
    assert.equal(new Set(theme.swatches).size,5);
    assert.ok(theme.swatches.every(s=>/^#[0-9a-f]{6}$/i.test(s)));
    const tokens=createThemeColors(theme.id);
    for(const [name,color] of Object.entries(tokens)){
      assert.match(color,/^#[0-9a-f]{6}$/i,theme.id+': '+name);
    }
    assert.notEqual(tokens.bg,tokens.text);
  }
});
test('body and panel text maintain WCAG AA contrast',()=>{
  for(const theme of THEMES){
    const C=createThemeColors(theme.id);
    assert.ok(contrast(C.text,C.bg)>=4.5,theme.id+' body '+contrast(C.text,C.bg));
    assert.ok(contrast(C.text,C.panel)>=4.5,theme.id+' panel '+contrast(C.text,C.panel));
  }
});
test('preferences are never identity, permission, scoring or billing controls',()=>{
  for(const theme of THEMES){
    const tokens=createThemeColors(theme.id);
    assert.ok(!('accountId' in tokens));
    assert.ok(!('jwt' in tokens));
    assert.ok(!('score' in tokens));
    assert.ok(!('billing' in tokens));
  }
});

test('fixed corporate colours exactly match latest approved brief',()=>{
  assert.deepEqual(BRAND, {
    slate:'#2A3439', mineral:'#5C6B73', mistBlue:'#9DB2BF',
    fog:'#DBE2EF', paper:'#F8FAFC', copper:'#C87D55', ink:'#0F172A',
  });
  assert.deepEqual(resolveTheme(DEFAULT_THEME).swatches,[
    BRAND.paper,BRAND.fog,BRAND.mistBlue,BRAND.mineral,BRAND.slate
  ]);
  assert.equal(createThemeColors(DEFAULT_THEME).text,BRAND.ink);
});
test('copper action contrast is accessible; copper must not be used as small text on white',()=>{
  assert.ok(contrast(BRAND.ink,BRAND.copper)>=4.5);
  assert.ok(contrast(BRAND.slate,BRAND.paper)>=7);
  assert.ok(contrast(BRAND.mineral,BRAND.paper)>=4.5);
  assert.ok(contrast(BRAND.copper,BRAND.paper)<4.5);
  assert.equal(createThemeColors(DEFAULT_THEME).action,BRAND.copper);
  assert.equal(createThemeColors(DEFAULT_THEME).onAction,BRAND.ink);
});
test('browser emblem and opening use the central brand palette, never old electric blue',()=>{
  const mark=readFileSync(new URL('./webBranding.js',import.meta.url),'utf8');
  const intro=readFileSync(new URL('../components/WebIntro.js',import.meta.url),'utf8');
  assert.match(mark,/BRAND\.slate/);
  assert.match(mark,/brandMarkDataUri/);
  const geometry=readFileSync(new URL('./logo-geometry.mjs',import.meta.url),'utf8');
  assert.match(geometry,/BRAND\.copper/);
  assert.doesNotMatch(mark,/#0A58FF|ELECTRIC_BLUE/);
  assert.match(intro,/BRAND\.copper/);
});
