import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=(p)=>readFileSync(new URL(p,import.meta.url),'utf8');
test('public landing is the actual rendered component, not a disconnected mockup',()=>{
 const root=read('../components/AuthScreen.tsx');
 const scene=read('../components/WorldExperience.js');
 assert.match(root,/if \(!showAuth\) return <WorldLanding onLogin=/);
 assert.match(scene,/export function WorldLanding/);
 assert.match(scene,/Explore the experience/);
 assert.match(scene,/Global ambition|International|INTERNATIONAL VISION|INTERNATIONAL/i);
});
test('private workspace is rendered with same cinematic design, functional pages and real API source',()=>{
 const shell=read('../App.web.js');
 const scene=read('../components/WorldExperience.js');
 for(const name of ['WorldSidebar','WorldToolbar','WorldHero','WorldAnalytics','WorldMarkets']){
  assert.match(shell,new RegExp('<'+name+'\\b'));
  assert.match(scene,new RegExp('export function '+name+'\\b'));
 }
 for(const tab of ['radar','opportunities','analytics','markets','profile','settings']){
  assert.match(scene,new RegExp("'"+tab+"'"));
 }
 assert.match(shell,/api\.opportunities/);
 assert.match(shell,/api\.stats/);
 assert.match(shell,/setSelected/);
});
test('public workspace preview cannot access customers or fabricate stats',()=>{
 const scene=read('../components/WorldExperience.js');
 assert.match(scene,/preview\?<View/);
 assert.match(scene,/WorldAnalytics preview/);
 assert.match(scene,/preview\?\[\]:items/);
 assert.match(scene,/preview\?'—'/);
 assert.match(scene,/No verified results loaded/);
 assert.doesNotMatch(scene,/supabase\.auth|api\.account|api\.opportunities/);
});
test('layout responds to breakpoints and is semantically accessible',()=>{
 const scene=read('../components/WorldExperience.js');
 const shell=read('../App.web.js');
 assert.match(scene,/width<760/);
 assert.match(shell,/width < 930/);
 assert.match(shell,/width < 1350/);
 assert.match(scene,/accessibilityRole="button"/);
});
test('night theme is selectable but corporate mark stays independent of account themes',()=>{
 const theme=read('./theme-system.mjs');
 const brand=read('../components/BrandLogo.js');
 assert.match(theme,/DEFAULT_THEME = 'command-night'/);
 assert.match(brand,/BRAND_MARK_PATHS/);
 assert.doesNotMatch(brand,/settings\.theme|createThemeColors/);
});
