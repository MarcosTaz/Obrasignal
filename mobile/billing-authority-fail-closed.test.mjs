import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';

const gate = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');

test('server billing authority failure cannot silently fall back to client entitlement', () => {
  assert.doesNotMatch(gate, /try\s*\{\s*server\s*=\s*await api\.billingStatus\(\);?\s*\}\s*catch\s*\([^)]*\)\s*\{\s*\}/);
  assert.doesNotMatch(gate, /plan:\s*server\?\.plan\s*\|\|\s*\(hasProEntitlement\(info\)\s*\?\s*['\"]pro['\"]/);
  assert.match(gate, /authority:\s*['\"]loading['\"]/);
  assert.match(gate, /authority:\s*['\"]ready['\"]/);
  assert.match(gate, /billing\.authority\s*!==\s*['\"]ready['\"]/);
});

test('billing authority outage is visible and retryable instead of rendering customer data', () => {
  assert.match(gate, /Não foi possível validar o estado da subscrição/);
  assert.match(gate, /Tentar novamente/);
  assert.match(gate, /onPress=\{refresh\}/);
});

test('server plan remains the access authority while store entitlement is only purchase metadata', () => {
  assert.match(gate, /plan:\s*server\.plan/);
  assert.match(gate, /pro:\s*server\.plan\s*===\s*['\"]pro['\"]/);
});
