import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  BILLING_PRODUCT,
  isCanonicalBillingProduct,
  selectProPackage,
} = require('./src/billingContracts.js');


test('canonical RevenueCat product identity is exact and base-plan compatible', () => {
  assert.equal(BILLING_PRODUCT, 'obrasignal_pro_monthly');
  assert.equal(isCanonicalBillingProduct('obrasignal_pro_monthly'), true);
  assert.equal(isCanonicalBillingProduct('obrasignal_pro_monthly:monthly'), true);
  assert.equal(isCanonicalBillingProduct('another_product'), false);
  assert.equal(isCanonicalBillingProduct('another_product:monthly'), false);
});


test('purchase package selection never falls back to an unrelated monthly package', () => {
  const unrelated = { packageType: 'MONTHLY', product: { identifier: 'another_product', priceString: '€1.99' } };
  const pro = { packageType: 'CUSTOM', product: { identifier: 'obrasignal_pro_monthly:monthly', priceString: '€9.99' } };

  assert.equal(selectProPackage({ availablePackages: [unrelated, pro] }), pro);
  assert.equal(selectProPackage({ availablePackages: [unrelated] }), null);
  assert.equal(selectProPackage({ availablePackages: [] }), null);
});


test('mobile Pro label is derived from backend state rather than SDK entitlement alone', () => {
  const source = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');
  assert.match(source, /const serverPro = server\?\.plan === 'pro' && server\?\.active === true;/);
  assert.match(source, /pro: serverPro,/);
  assert.doesNotMatch(source, /pro:\s*hasProEntitlement\(info\)/);
  assert.match(source, /backend_subscription_not_recognized/);
});
