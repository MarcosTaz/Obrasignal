# CERTACTUM — FACTORY STATE

## Canonical identity
**Product/company name: Certactum.** CausLedger is a retired working name. Legacy identifiers may remain only where changing them risks evidence lineage or compatibility. All new public/product/commercial work uses Certactum.

## Mission
Certactum is an evidence-first assisted recovery system for supplier-side customer-caused engineering/change cost and NRE recovery. Cost is not money owed. Source authenticity and recoverability are separate. Human review precedes action.

## Five-layer hardening program
A layer is not marked CLOSED merely because code exists. CLOSED requires verifiable evidence for every gate that can be executed internally; external dependencies remain explicitly EXTERNAL/PENDING and may not be represented as complete.

### L1 — Identity and authentication — ACTIVE
Internal gates:
- tenant derived from authenticated context, never caller body;
- operator/analyst/reviewer role separation and authorization denial tests;
- capture identity bound to actor and immutable evidence metadata;
- replay identity binding fails closed;
- independent review required before action;
- no upload may manufacture source authenticity.
External production gates:
- production identity provider configured;
- MFA enforced for privileged users;
- independently verified real operator/customer identity where required;
- privileged access/recovery process tested.

### L2 — Immutable originals / WORM / custody — NEXT
Internal gates:
- immutable provider abstraction;
- COMPLIANCE retention requirement;
- exact-version readback;
- SHA-256 + SHA-512 + byte-length verification;
- authorization scope/window/role/byte-limit binding;
- immutable collision/rebinding rejection;
- confidential export reads exact originals.
External production gates:
- real WORM/object-lock provider configured and tested;
- retention and legal-hold policy mapped to provider controls;
- provider receipt/readback evidence archived;
- backup/DR restore exercise completed without weakening immutability.

### L3 — External timestamp/signature/attestation — NEXT
Internal gates:
- cryptographic attestation target is deterministic and independently verifiable;
- trusted-list/service-state verification remains distinct from internal claims;
- no fabricated TSA/HSM/signature/public-anchor status.
External production gates:
- real qualified/trusted provider selected and configured;
- key custody/HSM controls evidenced where applicable;
- timestamp/signature verification tested, including historical service state;
- provider outage/failure mode fails closed.

### L4 — Proof Pack / independent verification — NEXT
Internal gates:
- durable lineage binds originals, outcome evidence, authorization and resolution audit;
- offline export contains exact originals;
- independent verifier rehashes evidence and rejects tamper;
- export target binding and append-only export audit;
- no documentary bytes in audit event.
External gate:
- independent third party can validate a supplied synthetic dossier without trusting Certactum runtime.

### L5 — Operational/legal security — NEXT
Internal gates:
- fail-closed release gates and explicit truth boundary;
- no real customer data before production controls;
- security/privacy/retention operational checklist and evidence register.
External gates:
- independent pentest/remediation;
- GDPR controller/processor mapping, DPA/privacy/retention/incident procedures reviewed;
- backup/DR and incident-response exercises;
- jurisdiction-specific legal review of evidentiary positioning; never promise court acceptance.

## Current technical truth
- Secure evidence capture is operator-only and authorization-scoped.
- Default runtime rejects raw inline documentary evidence outside the dedicated secure capture route.
- Tenant identity is derived from authenticated context.
- New assisted uploads identify provider as `certactum-assisted-intake` and remain source-authentication `UNVERIFIED`.
- Original evidence is bound to immutable/WORM facts with exact-version readback and fail-closed digest/length verification.
- Intake and outcome authorization scopes are independently recomputable and bounded.
- Capture replay identity includes content, content type, actor, authorization scope and normalized `effective_at`; semantic changes fail closed before provider writes.
- Independent review is required before action; final outcome evidence is separately authorized and ACTIONED-gated.
- Durable Proof Pack/offline export binds initial and outcome evidence and verifies exact originals independently.

## Repository truth
Branch: `apps/industrial-claims`
PR: `#785` — DRAFT, no merge/deploy.
Current hardening test commit before this state update: `f908a7d897ab13525be64f4dacadc1716d7c36f9`.
The preceding exact-head run on `0b007821a5e0a2ecc5367af191fa363e6301c4ba` produced 1291 passed, 2 skipped, and one unrelated Chile MercadoPublico temporal failure; mobile passed. Never modify that unrelated Chile test/code from this Factory. Exact-head CI must be rechecked after this state update.

## Production/commercial truth boundary
Do not claim production WORM/TSA/HSM, independent real-customer identity verification, paid audit, recovered money, pilot validation, court admissibility, or full production readiness without external evidence. `marcos@certactum.com` has demonstrated mail delivery; this is not equivalent to full mail-auth/reputation readiness. Certactum-related Vercel deployments exist; this is not proof of one complete canonical customer application.

## Release gates
No real customer documentary data until production identity, secure storage, access control and required operational controls are genuinely configured and verified. Do not fabricate provider receipts, seals, signatures, anchors, validation, payments or recoveries. Keep PR #785 DRAFT. No merge/deploy/production action without explicit production decision.

## ACTIVE → NEXT
ACTIVE: close every executable L1 identity/authentication gate with adversarial tests and explicit production-provider boundary.
NEXT: L2 immutable originals/WORM custody; then L3 external attestation; L4 independent Proof Pack; L5 operational/legal security. External owner/provider dependencies never stop completion of executable internal gates.
