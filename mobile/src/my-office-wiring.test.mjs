import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const file=readFileSync(new URL('../App.web.js',import.meta.url),'utf8');
test('canonical authentication still wraps web application',()=>{
  assert.match(file,/return <AuthGate><WebMain\/><\/AuthGate>/);
});
test('My Office stays behind disabled contract and routes through canonical tab selection',()=>{
  assert.match(file,/import \{ MY_OFFICE_ENABLED, MODULES, routeFor, translate \}/);
  assert.match(file,/MY_OFFICE_ENABLED && tab==='office'/);
  assert.match(file,/const target=routeFor\(module.id\);if\(target\)setTab\(target\)/);
});
test('existing authenticated Radar and Profile UI remain',()=>{
  assert.match(file,/<RadarPanel /);
  assert.match(file,/<ProfilePanel /);
  assert.match(file,/<OpportunityDetail /);
});
