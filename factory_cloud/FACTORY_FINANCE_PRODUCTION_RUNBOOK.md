# Factory Finance — Production Activation Runbook

This runbook separates engineering readiness from legal/fiscal/payment-provider authority. Completing code or Stripe TEST objects never implies live collection readiness.

## 1. Merchant identity / Stripe activation

Before any live write:

- choose and verify the operating legal/fiscal entity that is the merchant of record for the portfolio;
- complete Stripe production onboarding/KYC for that entity;
- provide the public business/product URL used by Stripe verification;
- the account owner must personally accept Stripe terms where required;
- verify `charges_enabled=true`, `payouts_enabled=true`, and no material account requirements remain due.

The K3 public product URL currently available for K3-specific verification is:

`https://k3-fatality.vercel.app`

Do not use this K3 URL as the umbrella merchant website for unrelated brands unless that accurately represents the operating entity and Stripe business profile.

## 2. Portugal fiscal-document boundary

Stripe Hosted Invoice is treated by Factory Finance as a **collection surface**, not as the canonical Portuguese fiscal-document authority.

For operations subject to Portuguese invoicing rules, the canonical fiscal document must be issued by an appropriate AT-authorized path, such as the Portuguese Tax Authority invoicing applications where applicable or an AT-certified invoicing program.

Relevant control themes include:

- sequential fiscal document identity;
- document series communication / ATCUD where applicable;
- QR code requirements for documents emitted by certified invoicing software where applicable;
- communication of invoice elements to the Portuguese Tax Authority;
- VAT/tax treatment determined by the operating entity, customer and transaction.

Factory Finance therefore requires a concrete external `fiscal_document_ref` before a live B2B Stripe collection invoice can be created or sent. Direct-bank B2B collection uses the same rule.

`FACTORY_PRODUCTION_FISCAL_INVOICE_READY=true` means the operating fiscal process has been independently established. It is not permission to manufacture a fiscal reference inside Factory Finance.

## 3. Payout bank

The production payout destination must be configured and verified in the payment provider. A repository value or test-mode bank configuration is not payout evidence.

For optional direct-bank invoices, the runtime may additionally use:

- `FACTORY_BILLING_IBAN`
- `FACTORY_BILLING_BIC`

These values belong in a deployment secret store only. Do not commit them to source, tests, screenshots, logs or PR descriptions.

Only set `FACTORY_PRODUCTION_PAYOUT_BANK_VERIFIED=true` after provider/account evidence confirms the intended payout bank is active.

## 4. Stripe provider runtime

Required runtime configuration:

- `FACTORY_STRIPE_SECRET_KEY`
- `FACTORY_STRIPE_WEBHOOK_SECRET`
- `FACTORY_STRIPE_LIVEMODE=true`
- `FACTORY_PRODUCTION_LEGAL_ENTITY_VERIFIED=true`
- `FACTORY_PRODUCTION_FISCAL_INVOICE_READY=true`
- `FACTORY_PRODUCTION_PAYOUT_BANK_VERIFIED=true`

Customer delivery remains separately disabled until explicitly enabled:

- `FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED=true`

All live Stripe writes fail closed unless the three production readiness declarations are true. Live B2B collection additionally requires the per-engagement external fiscal-document reference.

## 5. Webhook

Expose an HTTPS POST route that passes the **unaltered raw request body** and `Stripe-Signature` header to `factory_cloud.stripe_webhook_http.handle_stripe_webhook`.

Runtime must persist `FACTORY_FINANCE_LEDGER_PATH` on durable storage. Do not place the revenue ledger on an ephemeral serverless filesystem in production.

Provider requirements:

- production webhook endpoint registered with Stripe;
- production webhook signing secret stored as `FACTORY_STRIPE_WEBHOOK_SECRET`;
- `invoice.paid` used as Stripe invoice settlement evidence;
- K3 supporter flow uses paid `checkout.session.completed` evidence and never grants a paid entitlement;
- duplicate event IDs are idempotent; conflicting reuse fails closed.

## 6. Catalog

The B2B Stripe catalog is metadata-driven by `factory_id`. Product IDs are not hard-coded in source.

Before live catalog materialization:

- merchant identity must be correct;
- production activation gates must be green;
- run catalog discovery read-only first;
- reject duplicate active products for one `factory_id`;
- create missing live B2B products only with explicit `allow_create=True`.

No static catalog price is created for dynamic B2B fees. The engagement/fiscal process determines the amount.

## 7. Controlled live rehearsal

Do not claim production readiness from TEST evidence.

A controlled live rehearsal must prove, in order:

1. valid real merchant/customer identity appropriate to the rehearsal;
2. valid fiscal document or other legally appropriate document for the transaction;
3. live provider collection succeeds;
4. signed production webhook converges the ledger to `PAID`;
5. provider payout reaches the configured bank;
6. bank/provider evidence reconciles the revenue record to `RECONCILED`;
7. any rehearsal refund/credit-note requirements are handled correctly.

Never mark `PAID` or `RECONCILED` merely because a UI button was clicked.

## 8. Release condition

Production customer delivery may be enabled only when all of the following are proven:

- correct merchant/legal identity;
- Stripe KYC/account requirements complete;
- charges enabled;
- payouts enabled;
- payout bank verified;
- fiscal issuance path verified;
- per-engagement fiscal reference path verified;
- production webhook deployed and signed event ingestion proven;
- durable ledger storage deployed;
- controlled live settlement + bank reconciliation completed.

Until then, the Factory Finance system is production-capable engineering held behind external production gates, not a live money-moving system.
