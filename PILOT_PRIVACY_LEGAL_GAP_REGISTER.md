# ObraSignal — Pilot Privacy & Legal Gap Register

Status: `PRODUCT_PRIVACY_CONTROLS_EXIST / LEGAL_COMPLIANCE_NOT_CLAIMED / OWNER_LEGAL_BOUNDARIES_ISOLATED`

## Purpose

Prevent a technically strong account/privacy lifecycle from being misrepresented as completed legal compliance. This register separates executable product controls from decisions that require owner/legal authority before broad real-customer use.

## Product controls already represented in current candidate evidence

Current product/privacy lifecycle documents and tests describe:
- account-scoped export using authenticated server-side identity;
- explicit destructive deletion confirmation;
- tenant-scoped deletion with another tenant preserved;
- fail-closed inventory when a new account-scoped persistence owner is unclassified;
- distinction between shared public procurement truth and customer-private state;
- deletion `PENDING` while external Auth/Billing/device-cache revocation remains unproven;
- anti-resurrection tombstone behavior instead of silently recreating a deleted account;
- corrupt JSON/export state failing closed rather than being silently omitted.

These are product-safety controls. They do not by themselves establish GDPR, consumer, tax/accounting, ePrivacy/cookie, employment, marketing or contractual compliance.

## Owner/legal decisions required before broad commercial readiness

### Privacy notice

Need an externally approved notice covering actual personal-data categories, purposes, legal bases where applicable, retention approach, processors/subprocessors, user rights and contact route.

### Terms / customer agreement

Need an approved commercial agreement appropriate to the actual offer, including product scope, limitations, support expectations, billing/cancellation terms, liability allocation and acceptable use as applicable.

### Controller / processor roles

Determine actual roles for customer profile/user data, authentication provider data, billing data, notification provider data and any future customer-uploaded material. Do not guess these roles in product copy.

### Retention

Current system intentionally does not invent a statutory retention duration. Establish approved retention rules for account data, billing/accounting evidence, support/incident records and outreach records where required.

### Marketing/outreach basis

Before scaling outbound prospecting, confirm lawful/appropriate B2B contact practices, opt-out handling, suppression records and jurisdiction/channel rules. Current GTM preparation must not be interpreted as legal authorization to send.

### Cookies / tracking / analytics

If analytics or tracking beyond strictly necessary product operation is introduced, determine consent/notice requirements before enabling it. Do not add vanity tracking merely because the funnel needs measurement.

### Subprocessors / external services

Maintain the actual list of providers involved in authentication, hosting, billing, push notifications, email and any analytics/monitoring used with customer data. Provider configuration must match what notices/agreements say.

### Data subject / customer rights operations

Map how access/export, correction and deletion requests are received, authenticated, executed and recorded. Product endpoints are part of this workflow, not the whole legal procedure.

## Assisted-pilot rule

Before a real external pilot receives customer credentials/data:
- disclose the pilot nature and known limitations;
- use only data necessary for the pilot;
- avoid requesting secrets or unnecessary personal data;
- identify the support/privacy contact actually monitored;
- ensure the customer understands what information is sourced from public procurement data vs private company profile/workflow state;
- keep production billing inactive unless explicitly authorized and configured;
- do not claim legal compliance that has not been established.

## Completion state

`PRODUCT_PRIVACY_SAFETY_PARTIAL_GREEN / NOTICE_NOT_APPROVED / TERMS_NOT_APPROVED / RETENTION_POLICY_NOT_APPROVED / MARKETING_BASIS_NOT_APPROVED / SUBPROCESSOR_DISCLOSURE_NOT_FINAL / OWNER_OR_LEGAL_ACTION_REQUIRED`

These owner/legal boundaries do not stop independent engineering, support, GTM preparation or synthetic verification.
