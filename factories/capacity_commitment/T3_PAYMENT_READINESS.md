# Capacity Commitment — T3 Payment Readiness

Status: **COMMERCIAL COLLECTION READY IN PROCESS / STRIPE ACCOUNT EXTERNALLY BLOCKED**

Purpose: make the first paid pilot collectible without confusing proposal, PO, invoice, remittance, payment intent or settled cash.

## Current payment-rail truth

As of 2026-08-29, the Stripe connection visible to this execution exposes only an account named **K3 Fatality** in test and live mode.

That account belongs to another business/Factory and must **not** be used for Capacity Commitment.

Therefore:

- `CAPACITY_STRIPE_ACCOUNT = NOT_CONNECTED / UNKNOWN`
- `STRIPE_PAYMENT_LINK = NOT_CREATED`
- `STRIPE_PRODUCT = NOT_CREATED`
- `STRIPE_PRICE = NOT_CREATED`
- `PAYMENT_RECEIVED = NO`

Do not create Capacity Commitment products, prices, payment links, invoices or customers inside the K3 Fatality Stripe account.

## What is needed before a Stripe charge/link can be used

A Capacity Commitment / correct operating-company Stripe account must be connected and clearly identified.

Before creating any live payment object, confirm:

- correct legal seller/business identity;
- correct Stripe account/context;
- live mode intentionally selected;
- correct currency and amount;
- buyer/customer identity;
- agreed commercial scope exists;
- tax/VAT treatment is not guessed;
- billing address/VAT information requested only as necessary;
- invoice/payment description does not promise a recovery outcome.

## Default fixed-pilot collection hypothesis

Commercial hypothesis:

- UK bounded pilot: **£3,000**;
- Euro bounded pilot: **€3,500**;
- suggested first-pilot structure: **50% at start/data acceptance + 50% on delivery**.

This is not accepted pricing until a real buyer agrees.

If the buyer's procurement process requires a PO, supplier onboarding, invoice terms or bank transfer instead of card/Stripe, follow the buyer's legitimate procurement path rather than forcing Stripe.

## Payment-state ledger

Track independently:

1. `PRICE_DISCLOSED`
2. `PILOT_PROPOSED`
3. `PILOT_ACCEPTED_UNPAID`
4. `AGREEMENT_SIGNED` (if applicable)
5. `PO_RECEIVED` (if applicable)
6. `INVOICE_ISSUED`
7. `PAYMENT_LINK_SENT` (if applicable)
8. `PAYMENT_INITIATED`
9. `PAYMENT_RECEIVED`
10. `FUNDS_AVAILABLE` / settlement state when materially relevant
11. `REFUND_OR_REVERSAL` if applicable

No state implies the next.

`PO_RECEIVED != PAYMENT_RECEIVED`

`INVOICE_ISSUED != PAYMENT_RECEIVED`

`PAYMENT_LINK_SENT != PAYMENT_RECEIVED`

`CARD_AUTHORIZED != SETTLED_CASH` when settlement evidence matters.

## Description truth

A payment/invoice description should describe the bounded service, for example:

**Capacity Commitment Recovery Audit — one customer / one programme / one bounded period**

Do not describe the charge as:

- guaranteed recovery;
- recovered cash;
- claim proceeds;
- legal representation;
- settlement collection;
- success fee unless that model is actually agreed and appropriate.

## Hybrid model

Working hypothesis only:

- £1,250 / €1,500 setup;
- 7.5% of incremental cash actually received and attributable to the supported recovery action.

A success-fee amount cannot be invoiced merely from engine exposure, claim value, customer approval or disputed amount. The defined attributable cash receipt must actually occur under the agreed commercial terms.

## Buyer procurement intake

If a qualified buyer is ready to transact, collect only what their procurement/payment route actually requires, such as:

- legal entity;
- billing/contact email;
- billing address;
- VAT/tax identifier where applicable;
- PO/reference number if required;
- currency;
- agreed scope/price;
- payment terms;
- buyer procurement contact.

Do not put bank details, secrets or unrelated buyer data in public GitHub.

## Blocker handling

The missing correct Stripe account is **not** a reason to stop T3 conversion. A buyer may still progress through case qualification, proprietary data handoff, scope acceptance, supplier onboarding or signed commercial commitment.

If payment becomes immediately due before a correct rail is connected, mark `PAYMENT_RAIL_BLOCKED` and surface the exact buyer/payment requirement. Do not route funds through another Factory's account as a workaround.
