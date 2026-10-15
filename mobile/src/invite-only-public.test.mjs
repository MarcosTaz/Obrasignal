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
