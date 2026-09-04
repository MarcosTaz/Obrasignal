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
5. Operational/legal security — **INTERNAL CLOSED TO CURRENT TOOL BOUNDARY / EXTERNAL PENDING**.

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
- Stripe TEST Checkout completed a symbolic EUR 1.00 card payment and the payment was fully refunded successfully.
- Stripe LIVE Checkout completed a symbolic EUR 1.00 card payment with status `succeeded` and `CERTACTUM` statement descriptor suffix.
- The LIVE EUR 1.00 payment remains intentionally unrefunded by owner decision.
- The LIVE EUR 1.00 payment is technical validation only: it is not a paid customer, commercial subscription, validated sale, or recovered customer value.
- Billing state logic covers checkout completion, activation, failed renewal/past-due, recovery, cancellation and refund, with idempotency/collision gates.
- Final commercial plan/price and a recurring lifecycle exercise against that deliberate final plan remain pending; no price is invented merely to close a checklist.

## Production hosting/data truth — verified 2026-09-03
- Vercel canonical project: `changeclaim` (`prj_4mQZatta2MbhIPlnnyqhiD2eDbXT`). The legacy Vercel project slug is not the public product identity.
- Current production deployment `dpl_2h8zFm6WwodPHonK6VTV7BCznNXw` is READY.
- Domains attached include `certactum.com` and `www.certactum.com`; canonical www endpoint returns HTTP 200.
- Production root is a lightweight Vercel shell loading the application document from an external endpoint. Vercel READY/domain health is therefore not equivalent to browser-visible customer-journey validation.
- Connected Neon `certactum-core` schema contains organizations, projects, memberships, changes, notices, decisions, evidence, audit log and upload-token tables.
- Current database checkpoint: 1 organization, 1 project, 1 membership, 2 change records, 0 evidence records. No real confidential evidence is present in the evidence table at this checkpoint.

## Repository truth
Repository: `MarcosTaz/Obrasignal`.
Branch: `apps/industrial-claims`.
PR: `#785` — OPEN, DRAFT, not merged. Keep DRAFT; no merge/deploy from this PR without an explicit production decision.

Exact executable validation at `6fae35f4e2537eb534382616d0868faf6eb36734`, workflow `33683326028`: Mobile SUCCESS; Python `1310 passed, 2 skipped, 2 warnings, 1 failed`. The sole failure is the unrelated Chile MercadoPublico assertion; no Certactum-caused failure was observed. Later commits that only update state/evidence documentation do not alter executable Certactum code.

## Production data boundary
Do not accept real confidential customer documentary evidence until production identity/access/storage/data-handling controls required for that use are genuinely configured and verified. Do not claim production WORM/TSA/HSM, certification, court acceptance, guaranteed recovery, paid customer validation or real recovered value without external evidence.

## Remaining owner-visible / external gates
These are not silently closable by repository/database/HTTP inspection:
- Browser-visible verification of the canonical deployed application: approved final logo/favicon, navigation, login, Help, PT/EN/FR/ES and desktop/tablet/mobile behavior.
- Fresh-account production customer-zero walkthrough from onboarding to first verifiable dossier. This must not be simulated as completed from database state alone.
- Deliberate final commercial price/plan decision, followed by recurring Stripe lifecycle validation against that actual configuration.
- Explicit production release decision before merge/deploy from PR #785.

## External pending
- Production IdP configuration and privileged MFA/account recovery evidence.
- Production WORM/Object Lock provider receipts and DR exercise.
- Real qualified/trusted timestamp/signature provider and historical validation.
- Independent pentest/remediation.
- GDPR/DPA/privacy/retention/incident review.
- Jurisdiction-specific evidentiary/legal review where required.

## ACTIVE → NEXT
ACTIVE: internal executable hardening is exhausted to the current tool/evidence boundary without a known Certactum-caused test failure.
NEXT: browser-visible customer-zero verification → deliberate price/plan → explicit production release decision → external trust upgrades.

## Release boundary
The application may be used for commercial presentation and lead capture. Real confidential documentary intake remains blocked until the required production identity/access/storage/data-handling controls are genuinely configured and verified. External certification/trust upgrades may follow revenue where appropriate; core production identity, access control, secure storage and data-handling controls cannot be bypassed.
