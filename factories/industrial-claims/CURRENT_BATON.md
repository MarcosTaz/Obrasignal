# VINDORUM — CURRENT BATON

Updated: 2026-09-04

## MISSION
Reach a genuinely zero-touch customer E2E: the customer understands, qualifies, pays, submits evidence securely, confirms extracted facts, receives a dossier and tracks recovery without routine operator intervention from us.

## ACTIVE
`RELEASE_PREFLIGHT → DEDICATED_DEPLOY → DOMAIN/TLS → VINDORUM MERCHANT BILLING → SECURE_INTAKE LIVE PROBES → DEDICATED SENDER → CUSTOMER_ACQUISITION → FIRST_PAID_SCAN`

## CURRENT TRUTH
- canonical company/product brand: VINDORUM
- identity cleanup merged through PR #958
- last identity-clean main SHA: `b8acd4585eee6390040652794284c4222f08c32b`
- normal-path operator intervention target: 0
- `vindorum.com`: observed available, not purchased
- dedicated VINDORUM Vercel project: not present in the connected team
- VINDORUM sender: not provisioned
- live Stripe session currently exposes an account named `Obrasignal`; it is not approved as VINDORUM merchant identity
- production confidential intake: disabled until production auth plus live WORM and trusted-timestamp probes pass
- production paid checkout: not yet verified/live for VINDORUM
- paid customer: none proven
- customer recovery: none proven

## RELEASE TRUTH
Release states are deliberately separate:
1. metadata site release-ready requires owned canonical domain, verified TLS, dedicated VINDORUM deployment and exact deployed release SHA;
2. paid Recovery Scan backend additionally requires VINDORUM-approved merchant identity, verified live billing, signed webhook roundtrip and secure-intake readiness;
3. full commercial launch additionally requires a verified sender on the canonical VINDORUM domain.

A live public page never implies the paid scan or commercial operation is live. A paid CTA must remain locked until the paid backend gate is truly ready.

## RESUME_AT
`EXACT_HEAD_CI → MERGE RELEASE PREFLIGHT → CREATE/VERIFY DEDICATED VINDORUM DEPLOYMENT → ACQUIRE/VERIFY CANONICAL DOMAIN → ESTABLISH VINDORUM MERCHANT + SENDER → LIVE TRUST PROBES → ENABLE PAID CTA → FIRST REAL CUSTOMER`
