# Factory Cloud Shared Billing Core

## Purpose

Provide one fail-closed financial routing layer for every registered Factory instead of implementing payment logic independently in each product.

## Current routing policy

- `obrasignal`: existing RevenueCat/store subscription authority (`pro`, `obrasignal_pro_monthly`).
- ObraSignal specialist/sub-Factories: inherit ObraSignal billing rather than creating duplicate customer subscriptions.
- Business/developing Factories: one shared B2B invoice owner contract with two collection rails: Stripe Hosted Invoice and optional direct bank transfer.
- `k3-fatality`: supporter contribution only for now; no paid entitlement and no subscription.
- Internal Factory Cloud: non-billable.
- Specialist support lanes can explicitly inherit the customer-facing owner product.

Every Factory newly added to the central registry is automatically covered by its group default unless an explicit override is required. The current registry contains 42 Factories and 29 distinct billing owners; inheriting lanes do not create duplicate billable products.

## Provider catalog

Provider object IDs are deliberately **not** committed to this public repository. Runtime/provider discovery uses stable metadata such as `factory_id` and `engagement_id` rather than hard-coded Stripe IDs.

A Stripe TEST catalog has been materialized externally for the current 26 B2B billing owners. Each B2B product has no fixed price. This is intentional: a pilot fee, fixed engagement or success fee is generated from an approved engagement/fee event, not invented from a static catalog price.

K3 has a separate TEST supporter product with a customer-selected EUR amount. It is not recurring and grants no paid entitlement.

## B2B collection

The canonical B2B flow is:

`ENGAGEMENT -> FEE_EARNED -> INVOICE_APPROVED -> STRIPE INVOICE -> PAYMENT_PENDING -> PAID -> RECONCILED`

Stripe Hosted Invoice is the default provider-backed collection surface. Direct bank transfer is an optional second rail, especially for larger B2B fees. The presence or absence of a direct-bank secret must not prevent Stripe invoice creation.

Customer recovery and our fee remain separate. Example:

- verified customer recovery: EUR 400,000;
- agreed success fee: 15%;
- platform revenue: EUR 60,000.

Only EUR 60,000 becomes our invoice/revenue truth. The EUR 400,000 remains customer recovery truth and is never treated as our revenue or routed through our account merely because the platform discovered it.

## Durable revenue truth

`revenue_ledger.py` owns a persistent SQLite ledger with:

- unique `(factory_id, engagement_id)` revenue identity;
- separate `recovery_amount` and `platform_fee_amount`;
- append-only state transition history;
- provider customer/invoice/payment references that cannot be silently replaced;
- provider-event idempotency by `(provider, provider_event_id)`;
- payload hashes instead of raw provider webhook payload persistence;
- conflict detection when the same provider event ID is reused with different evidence;
- portfolio/factory reporting without conflating customer recovery with platform revenue.

Standard revenue lifecycle:

`NOT_BILLABLE -> FEE_EARNED -> INVOICE_APPROVED -> INVOICED -> PAYMENT_PENDING -> PAID -> RECONCILED`

Subscription/supporter payments may use:

`NOT_BILLABLE -> PAYMENT_PENDING -> PAID -> RECONCILED`

`PAID` and `RECONCILED` require a durable bank/provider evidence reference. UI action alone can never mark a payment paid.

## Stripe provider adapter

`stripe_billing_provider.py` provides a production-capable but fail-closed Invoicing adapter. It:

- requires runtime Stripe secret and webhook secrets;
- requires an explicit livemode setting and rejects provider responses/webhooks from the wrong mode;
- uses deterministic idempotency keys per customer/engagement/operation;
- creates invoice items and invoices in EUR without handling raw card/bank credentials;
- finalizes invoices without automatically sending them;
- requires `FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED=true` before an invoice can be sent to a customer;
- verifies Stripe webhook HMAC signatures and timestamp tolerance;
- accepts only `invoice.paid` with complete Factory identity as payment evidence.

Required runtime variables when the Stripe provider is activated:

- `FACTORY_STRIPE_SECRET_KEY`
- `FACTORY_STRIPE_WEBHOOK_SECRET`
- `FACTORY_STRIPE_LIVEMODE`
- `FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED`

No secret is committed to Git.

## Bank destination

The direct-transfer IBAN is intentionally **not stored in this repository**. Runtime configuration may provide:

- `FACTORY_BILLING_IBAN`
- optional `FACTORY_BILLING_BIC`

The core validates the IBAN checksum. Ordinary billing route inspection only exposes whether direct bank transfer is configured plus a masked IBAN. Full bank instructions require an explicit call path and a valid runtime secret.

Do not put an owner or company IBAN in Git history, application source, tests, screenshots, logs or PR descriptions. Configure it in the deployment secret store only.

## TEST evidence — 2026-08-29

External Stripe TEST execution has proven the provider-side shape without live money:

1. the K3 voluntary supporter product and test payment link were created with no subscription/entitlement;
2. the 26 current B2B billing owners were materialized as separate dynamic-price TEST products identified by `factory_id` metadata;
3. a reserved-domain synthetic customer was created;
4. a WarrantyGuard synthetic case represented EUR 400,000 customer recovery and a 15% platform fee of EUR 60,000;
5. a EUR 60,000 Stripe invoice was created from that fee, finalized to `open`, and retained the Factory/engagement metadata;
6. no real customer email was used, no live payment occurred, and no bank/payout mutation occurred.

One deliberate failing-before was observed: `send_invoice` creation rejected a synthetic customer without email. The test was corrected with a reserved `example.com` address; no real message was transmitted. This is preserved as evidence that Stripe/customer-data prerequisites fail closed rather than being silently bypassed.

## K3 decision gate

K3 starts with voluntary supporter contributions, free core access and no subscription entitlement. A subscription can be introduced later only as a separate commercial experiment tied to recurring premium analytical value and evidence of willingness to pay, not merely access to basic probability outputs.

## Production gates still external

This branch is not permission to move money. Before live commercial activation, the owner/runtime must still establish and verify:

- the correct production legal entity/merchant account;
- Stripe production KYC/merchant activation;
- the production payout bank destination;
- production webhook endpoint + signing secret;
- customer-facing invoice branding/identity;
- Portugal/EU fiscal invoice and VAT/e-invoicing requirements for the operating entity;
- the direct-transfer IBAN secret only if that rail is used;
- explicit production customer-delivery enablement.

Until those gates are satisfied, TEST evidence is engineering proof only, not evidence of live revenue collection or bank settlement.
