# CERTACTUM — FACTORY STATE

## Canonical identity
**Product/company name: Certactum.** CausLedger is a retired working name and may appear only in legacy internal identifiers where changing it could damage compatibility or evidence lineage. No current public, commercial, domain, email or operating instruction may use the retired name.

Canonical domain: `certactum.com` / `www.certactum.com`.
Canonical business mailbox: `marcos@certactum.com`.

## Mission
Certactum is an evidence-first assisted recovery and proof system. It reconstructs customer-driven commercial/change events, preserves evidence lineage, separates documented cost from recoverability, requires human review before action, and produces independently verifiable dossiers. Source authenticity and recoverability are separate truth dimensions.

## Five-layer hardening state
1. Identity/authentication — **INTERNAL CLOSED / EXTERNAL PENDING**.
2. Immutable originals/WORM/custody — **INTERNAL CLOSED / EXTERNAL PENDING**.
3. External timestamp/signature/attestation — **INTERNAL CLOSED / EXTERNAL PENDING**.
4. Proof Pack/independent verification — **INTERNAL CLOSED / EXTERNAL PENDING**.
5. Operational/legal security — **INTERNAL ACTIVE / EXTERNAL PENDING**.

External dependencies do not stop executable internal work. They remain explicit and may not be represented as completed before evidence exists.

## Current product truth
- Tenant identity is derived from verified authentication context, not request body.
- JWT tenant identity can use a provider-managed signed claim independently from user subject and fails closed when required but absent/invalid.
- Analyst/reviewer/operator separation and cross-tenant denial are tested.
- Secure real-document capture is authorization-scoped, actor-bound, byte-bounded and immutable-store bound.
- Source authentication remains UNVERIFIED unless independently established; upload does not manufacture authenticity.
- Semantic replay/rebinding changes fail closed before duplicate immutable-provider writes.
- Independent review precedes action.
- Final outcome evidence has separate authorization and is bound into durable Proof Pack lineage.
- Confidential offline export retrieves exact originals, rehashes them independently and is audit logged.
- Backup/restore performs integrity validation, explicit SHA-256 binding, tamper rejection and atomic restore.
- Readiness diagnostics, customer-zero abuse tests and repeated tenant-scoped queue reads exist.
- Help content exists in PT/EN/FR/ES; confidential documents must not be sent by ordinary email without authorized intake.

## Stripe / commercial-flow truth — verified 2026-09-03
- Connected Stripe business identity is Certactum.
- Stripe TEST Checkout completed a symbolic EUR 1.00 card payment.
- The TEST EUR 1.00 payment was fully refunded successfully, proving executable refund flow without touching live funds.
- Stripe LIVE Checkout completed a symbolic EUR 1.00 card payment with status `succeeded` and `CERTACTUM` statement descriptor suffix.
- The LIVE EUR 1.00 payment remains intentionally unrefunded by owner decision.
- The LIVE EUR 1.00 payment is technical validation only: it is not a paid customer, commercial subscription, validated sale, or recovered customer value.
- Final commercial plan/price and recurring lifecycle exercise remain pending.

## Production hosting truth — verified 2026-09-03
- Vercel canonical project: `changeclaim` (`prj_4mQZatta2MbhIPlnnyqhiD2eDbXT`). The legacy Vercel project slug is not the public product identity.
- Current production deployment `dpl_2h8zFm6WwodPHonK6VTV7BCznNXw` is READY.
- Domains attached: `certactum.com`, `www.certactum.com`, plus Vercel aliases.
- `certactum.com` redirects permanently to `www.certactum.com`.
- `www.certactum.com` returned HTTP 200 through the authenticated Vercel fetch on 2026-09-03.
- No error/fatal runtime logs were found in the inspected 24-hour production window.
- The production root is currently a lightweight Vercel shell which loads the application document from an external Neon-hosted endpoint. Therefore Vercel READY/domain health is not equivalent to full browser/customer-journey validation.

## Repository truth
Repository: `MarcosTaz/Obrasignal`.
Branch: `apps/industrial-claims`.
PR: `#785` — OPEN, DRAFT, not merged. Keep DRAFT; no merge/deploy from this PR without an explicit production decision.

Latest PR head before this state correction: `70d7ff0e090e021c8835f97f21896eed478809f5`.
A prior exact source validation at `6fae35f4e2537eb534382616d0868faf6eb36734` produced 1310 passed, 2 skipped, 2 warnings; Mobile passed. The sole repository-wide failure in that run was the unrelated Chile MercadoPublico temporal assertion. Current later-head workflow evidence must not be called green unless revalidated exactly.

## Production data boundary
Do not accept real confidential customer documentary evidence until production identity/access/storage/data-handling controls required for that use are genuinely configured and verified. Do not claim production WORM/TSA/HSM, certification, court acceptance, guaranteed recovery, paid customer validation or real recovered value without external evidence.

## Remaining internal launch gates
- Visually/browser-verify the canonical deployed app: final logo/favicon, navigation, scroll behavior, login, Help, PT/EN/FR/ES and desktop/tablet/mobile behavior.
- Record a fresh-account customer-zero walkthrough from onboarding to first verifiable dossier on the canonical deployed application.
- Fix any Certactum defects discovered without redesigning the approved visual identity.
- Run exact-head Certactum/repository CI after the final internal fixes and preserve the exact result.
- Fix commercial Stripe configuration only after final price/plan is deliberately chosen; do not invent pricing merely to close a technical checklist.

## External pending
- Production IdP configuration and privileged MFA/account recovery evidence.
- Production WORM/Object Lock provider receipts and DR exercise.
- Real qualified/trusted timestamp/signature provider and historical validation.
- Independent pentest/remediation.
- GDPR/DPA/privacy/retention/incident review.
- Jurisdiction-specific evidentiary/legal review where required.

## ACTIVE → NEXT
ACTIVE: verify canonical deployed customer journey and eliminate remaining brand/UX inconsistencies.
NEXT: fresh-account customer-zero walkthrough → correct defects → exact-head CI → deliberate launch decision.

## Release boundary
The application may be prepared for commercial launch and lead capture, but real confidential documentary intake remains subject to the production-control boundary above. External certification/trust upgrades may follow revenue where appropriate; core production identity, access control, secure storage and data-handling controls cannot be bypassed.
