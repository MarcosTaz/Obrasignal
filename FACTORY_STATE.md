# CERTACTUM — FACTORY STATE

## Canonical identity
**Product/company name: Certactum.** CausLedger is a retired working name. Legacy identifiers may remain only where changing them risks evidence lineage or compatibility. All new public/product/commercial work uses Certactum.

## Mission
Certactum is an evidence-first assisted recovery system for supplier-side customer-caused engineering/change cost and NRE recovery. Cost is not money owed. Source authenticity and recoverability are separate. Human review precedes action.

## Five-layer hardening program
A layer is not marked CLOSED merely because code exists. Internal closure requires executable gates and adversarial tests. External dependencies remain EXTERNAL/PENDING and may not be represented as complete.

### L1 — Identity and authentication — INTERNAL CLOSED / EXTERNAL PENDING
Internal evidence:
- tenant derived from verified identity, never caller body;
- signed JWT tenant claim can be configured independently from user `sub`;
- missing/invalid configured tenant claim fails closed;
- operator/analyst/reviewer role separation;
- capture/replay actor and authorization scope binding;
- independent review before action;
- upload cannot manufacture source authenticity.
External pending: production IdP, privileged MFA, real-identity verification where required, tested account recovery.

### L2 — Immutable originals / WORM / custody — INTERNAL CLOSED / EXTERNAL PENDING
Internal evidence:
- immutable provider abstraction and COMPLIANCE retention requirement;
- exact-version readback;
- SHA-256/SHA-512/byte-length binding;
- authorization scope/window/role/byte-limit binding;
- collision/rebinding rejection;
- confidential export reads exact originals;
- SQLite operational backup/restore utility now performs online backup, integrity checks, explicit SHA-256 binding, tamper rejection and atomic restore.
External pending: production object-lock/WORM provider, provider legal-hold/retention controls, archived provider receipts, production DR exercise.

### L3 — External timestamp/signature/attestation — INTERNAL CLOSED / EXTERNAL PENDING
Internal evidence:
- deterministic cryptographic attestation target;
- trusted-list/service-state verification separated from internal assertions;
- fail-closed provider bundle and no fabricated TSA/HSM/signature/public-anchor status.
External pending: real qualified/trusted provider, key/HSM custody evidence, historical timestamp/signature validation and outage exercise.

### L4 — Proof Pack / independent verification — INTERNAL CLOSED / EXTERNAL PENDING
Internal evidence:
- durable lineage binds originals, outcome evidence, authorization and resolution audit;
- offline export contains exact originals;
- independent verifier rehashes evidence and rejects tamper;
- export target binding and append-only export audit;
- no documentary bytes in audit event.
External pending: independent third party validation of a supplied synthetic dossier without trusting Certactum runtime.

### L5 — Operational/legal security — INTERNAL ACTIVE / EXTERNAL PENDING
Internal completed:
- fail-closed release gates and explicit truth boundary;
- no real customer data before production controls;
- verified local database backup/restore primitive with tamper rejection;
- public identity migrated to Certactum on current customer-facing surfaces;
- console flow hardened against duplicate submissions, stale scroll restoration and manual first queue load.
Internal next:
- observability/readiness diagnostics without secrets;
- load/performance and failure-path tests;
- support/help/customer-zero adversarial journey;
- final release checklist/evidence register.
External pending: independent pentest/remediation, GDPR/DPA/privacy/retention/incident review, production backup/DR and incident-response exercises, jurisdiction-specific legal review. Never promise court acceptance.

## Current technical truth
- Secure evidence capture is operator-only and authorization-scoped.
- Default runtime rejects raw inline documentary evidence outside the dedicated secure capture route.
- Tenant identity is derived from authenticated context and can be separated from JWT user subject through a verified configurable tenant claim.
- New assisted uploads identify provider as `certactum-assisted-intake` and remain source-authentication `UNVERIFIED`.
- Original evidence is bound to immutable/WORM facts with exact-version readback and fail-closed digest/length verification.
- Intake and outcome authorization scopes are independently recomputable and bounded.
- Capture replay identity includes content, content type, actor, authorization scope and normalized `effective_at`; semantic changes fail closed before provider writes.
- Independent review is required before action; final outcome evidence is separately authorized and ACTIONED-gated.
- Durable Proof Pack/offline export binds initial and outcome evidence and verifies exact originals independently.
- Current customer-facing console/public capture identity is Certactum; retired CausLedger naming is retained only where compatibility/lineage requires it.

## Repository truth
Branch: `apps/industrial-claims`
PR: `#785` — DRAFT, no merge/deploy.
Validated exact head before backup/restore additions: `278efaf4dcc8609c8d0da9462de331b7633a0596`.
That run produced 1295 passed, 2 skipped and exactly one unrelated Chile MercadoPublico temporal failure; mobile passed. Never modify that unrelated Chile test/code from this Factory. Backup/restore commits require a new exact-head CI check.

## Production/commercial truth boundary
Do not claim production WORM/TSA/HSM, independent real-customer identity verification, paid audit, recovered money, pilot validation, court admissibility, or full production readiness without external evidence. `marcos@certactum.com` has demonstrated mail delivery; this is not equivalent to full mail-auth/reputation readiness. Certactum-related Vercel deployments exist; this is not proof of one complete canonical customer application.

## Release gates
No real customer documentary data until production identity, secure storage, access control and required operational controls are genuinely configured and verified. Do not fabricate provider receipts, seals, signatures, anchors, validation, payments or recoveries. Keep PR #785 DRAFT. No merge/deploy/production action without explicit production decision.

## ACTIVE → NEXT
ACTIVE: L5 observability/readiness diagnostics and operational failure-path hardening.
NEXT: load/performance → support/help/customer-zero adversarial journey → final internal release evidence register. External owner/provider dependencies do not stop executable internal work.