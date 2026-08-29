# Factory Cloud Shared Billing Core

## Purpose

Provide one fail-closed financial routing layer for every registered Factory instead of implementing payment logic independently in each product.

## Current routing policy

- `obrasignal`: existing RevenueCat/store subscription authority (`pro`, `obrasignal_pro_monthly`).
- ObraSignal specialist/sub-Factories: inherit ObraSignal billing rather than creating duplicate customer subscriptions.
- Business/developing Factories: shared B2B invoice + bank-transfer rail.
- `k3-fatality`: supporter contribution only for now; no paid entitlement and no subscription.
- Internal Factory Cloud: non-billable.
- Specialist support lanes can explicitly inherit the customer-facing owner product.

Every Factory newly added to the central registry is automatically covered by its group default unless an explicit override is required.

## Bank destination

The IBAN is intentionally **not stored in this repository**. Runtime configuration must provide:

- `FACTORY_BILLING_IBAN`
- optional `FACTORY_BILLING_BIC`

The core validates the IBAN checksum and fails closed if a B2B invoice requests payment instructions without a configured valid destination.

Do not put an owner or company IBAN in Git history, application source, tests, screenshots, logs or PR descriptions. Configure it in the deployment secret store only.

## Revenue truth

Customer recovery and our revenue are separate facts.

Example: a verified customer recovery of EUR 400,000 with a 15% success fee produces a platform fee of EUR 60,000. The EUR 400,000 remains customer recovery truth; only EUR 60,000 is platform revenue truth.

Standard revenue lifecycle:

`NOT_BILLABLE -> FEE_EARNED -> INVOICE_APPROVED -> INVOICED -> PAYMENT_PENDING -> PAID -> RECONCILED`

Subscription/supporter payments may use:

`NOT_BILLABLE -> PAYMENT_PENDING -> PAID -> RECONCILED`

`PAID` and `RECONCILED` require a durable bank/provider evidence reference. UI action alone can never mark a payment paid.

## Safety boundary

This module performs no real RevenueCat, Stripe, banking or payment-provider call. It creates a common routing/ledger contract and deliberately leaves production provider activation behind explicit secret/configuration and provider-account setup.

## K3 decision gate

K3 starts with voluntary supporter contributions, free core access and no subscription entitlement. This avoids forcing a subscription before recurring willingness-to-pay has been demonstrated. A subscription can be introduced later only as a separate commercial experiment tied to recurring premium analytical value, not merely access to basic probability outputs.
