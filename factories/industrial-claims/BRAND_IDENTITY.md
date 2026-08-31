# CAUSLEDGER — CANONICAL BRAND IDENTITY

## Canonical identity
- Brand: **CausLedger**
- Canonical domain: **causledger.com**
- Primary founder/business email: **marcos@causledger.com**
- Primary descriptor: **Supplier-side customer-caused cost & margin recovery**
- Initial wedge: **Customer-directed engineering/change cost (NRE / change-driven incremental cost)**
- Delivery model: **Assisted recovery — software + human review + evidence traceability + professional dossier**

## Public identity rules
All new public-facing assets for this Factory must use `CausLedger` as the product/business name. Do not introduce alternate public brands such as ChangeClaim, Industrial Claims, RecoveryLedger, ClaimLedger, or ad-hoc variants.

Website, email, proposals, invoices, receipts, payment pages, customer-facing dossiers, security notices and outreach must use the same canonical identity.

## Canonical customer-facing endpoints
- Web: `https://causledger.com` (pending domain purchase/activation)
- Email: `marcos@causledger.com` (pending mailbox activation)
- Recommended aliases once the mailbox domain is active: `claims@causledger.com`, `cases@causledger.com`, `billing@causledger.com`, `security@causledger.com`
- Sender display: `Marcos Moutinho | CausLedger`

## Payment identity
CausLedger must use a dedicated Stripe account / merchant identity. Do not use the Stripe account branded for another Factory or business. Checkout, invoices and receipts must present `CausLedger` consistently.

Initial payment model for assisted B2B delivery:
1. Rapid Recovery Scan — one-time scoped payment or invoice.
2. Single-case Forensic Recovery Audit — fixed-fee invoice, optionally split start/delivery.
3. Optional success component only when separately agreed and legally/commercially appropriate.

High-ticket B2B work should default to Stripe Invoicing / bank transfer + card support rather than forcing a generic self-serve subscription checkout.

## Authentication / trust requirements
Before accepting confidential customer documents through the web, CausLedger must have:
- real authenticated user/session boundary;
- tenant/customer isolation;
- secure upload/storage path;
- documented retention/deletion policy;
- privacy and security contact;
- no public/raw document persistence;
- SPF, DKIM and DMARC on `causledger.com` before material outbound email volume.

Until those controls are active, the web may explain the service and collect low-sensitivity lead/contact information, but must not imply confidential document intake is production-safe.

## Truth rules
- Cost is not automatically money owed.
- NO CLAIM / NEEDS REVIEW is a valid outcome.
- No recovery, entitlement, liability, payment or willingness-to-pay claim without evidence.
- External claim submission remains authority-gated.

## Migration rule
The existing ChangeClaim Vercel shell is a temporary preview only. It must be rebranded or replaced before being treated as the CausLedger production website.
