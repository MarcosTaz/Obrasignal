import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../components/AuthScreen.tsx',import.meta.url),'utf8');
test('anonymous UI has request invitation, not account creation',()=>{
 assert.match(source,/Pedir convite/);
 assert.match(source,/Solicitar convite/);
 assert.doesNotMatch(source,/supabase\.auth\.signUp\s*\(/);
 assert.doesNotMatch(source,/onSignup/);
});
test('existing customers retain authentication and recovery',()=>{
 assert.match(source,/supabase\.auth\.signInWithPassword/);
 assert.match(source,/supabase\.auth\.resetPasswordForEmail/);
});
test('review stage is NOT claimed to be backend invitation enforcement',()=>{
 assert.doesNotMatch(source,/convite verificado no servidor/i);
});

test('official vector is the only landing brand artwork',()=>{
 assert.ok(source.includes('/obrasignal-logo.svg'));
 assert.ok(!source.includes('Obra<Text style='));
});

test('transparent official vector assets are in the web public root',()=>{
 const svg=readFileSync(new URL('../public/obrasignal-logo.svg',import.meta.url),'utf8');
 const monogram=readFileSync(new URL('../public/obrasignal-monogram.svg',import.meta.url),'utf8');
 for(const asset of [svg,monogram]){
   assert.match(asset,/<svg\\b/);
   assert.match(asset,/<path\\b|<polygon\\b|<rect\\b/);
   assert.doesNotMatch(asset,/<image\\b/i);
 }
});
test('release workflow blocks publishing if provider signup is not proved disabled',()=>{
 const workflow=readFileSync(new URL('../../.github/workflows/web-preview.yml',import.meta.url),'utf8');
 assert.match(workflow,/Fail closed when production Auth allows public sign-up/);
 assert.match(workflow,/disable_signup/);
 assert.match(workflow,/RELEASE_BLOCKED: public sign-up is not proven disabled/);
 const gate=workflow.indexOf('Fail closed when production Auth allows public sign-up');
 const publish=workflow.indexOf('Deploy to GitHub Pages');
 assert.ok(gate>0 && publish>gate);
});
