import assert from 'node:assert/strict';
import fs from 'node:fs';

const billing = fs.readFileSync(new URL('./src/billing.js', import.meta.url), 'utf8');
const gate = fs.readFileSync(new URL('./components/BillingGate.js', import.meta.url), 'utf8');
const envExample = fs.readFileSync(new URL('./.env.example', import.meta.url), 'utf8');

assert.match(billing, /EXPO_PUBLIC_REVENUECAT_PURCHASE_LINK/);
assert.match(billing, /url\.hostname !== 'pay\.rev\.cat'/);
assert.match(billing, /includes\('\/sandbox\/'\)/);
assert.match(billing, /encodeURIComponent\(String\(appUserId\)\)/);
assert.match(billing, /if \(!base \|\| !appUserId\) return null/);
assert.match(gate, /appUserId: session\.user\.id/);
assert.match(gate, /providerReady: server\?\.provider\?\.commercial_ready === true/);
assert.match(gate, /hostedCheckoutReady = billing\.providerReady && clientHostedConfigured/);
assert.match(gate, /sdkCheckoutConfigured = billing\.providerReady && clientSdkConfigured/);
assert.match(gate, /if \(!billing\.providerReady\)/);
assert.match(gate, /Nenhum pagamento foi iniciado/);
assert.match(gate, /webPurchaseUrl\(billing\.appUserId\)/);
assert.match(gate, /Abrir checkout seguro/);
assert.match(gate, /Já paguei · atualizar estado/);
assert.match(gate, /server\.plan === 'pro'/);
assert.match(envExample, /EXPO_PUBLIC_REVENUECAT_PURCHASE_LINK=/);

console.log('Web billing regression contract passed.');
