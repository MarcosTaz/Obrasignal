# CERTACTUM — FACTORY STATE

## Canonical identity

**Product/company name: Certactum.**

CausLedger was a previous working name and is no longer the public or commercial identity. Legacy module names, historical commits, test names, database identifiers, or compatibility surfaces may retain the old name temporarily where changing them would risk evidence lineage or compatibility. All new product, commercial, documentation, UI, domain, email, and release work must use **Certactum**.

## Mission

Certactum is an evidence-first assisted recovery system for supplier-side customer-caused engineering/change cost and NRE recovery. It secures documentary evidence, deterministically analyzes potential recoverability, requires independent human review before action, records documented outcomes, and produces a durable verifiable Proof Pack/offline dossier.

Cost is not treated as money owed. Source authenticity and recoverability are separate. Valid outcomes include candidate, NEEDS REVIEW, and NO CLAIM.

## Current technical truth

- Secure evidence capture is operator-only and authorization-scoped.
- Default runtime rejects raw inline documentary evidence outside the dedicated secure capture route.
- Tenant identity is derived from authenticated context, not caller-supplied body fields.
- Secure capture forces source-authentication state to UNVERIFIED; upload does not manufacture authenticity.
- Original evidence is bound to immutable/WORM storage facts with exact-version readback and fail-closed hash/length verification.
- Intake authorization is bounded by tenant, case, purpose, roles, chronology, retention, transfer channel, byte limits and data terms; persisted authorization scope is independently recomputable.
- Authorization windows are enforced at registry time and boolean byte limits are rejected.
- Secure case analysis and amendment use registered evidence IDs rather than documentary content.
- Independent review is required before action.
- Final outcome evidence has a separate authorization scope and may only be captured for a current ACTIONED finding before any immutable-provider write.
- Secure capture performs registry preflight: exact retries are idempotent and do not duplicate immutable-provider writes; changed binding/content fails closed before provider write.
- Secure outcome registry explicitly rejects finding/source rebinding.
- Durable Proof Pack binds initial evidence, outcome evidence, resolution audit lineage and authorization scope.
- Confidential offline export requires exact original bytes, independently verifies the resulting dossier, uses no-store semantics and records an append-only export audit event without documentary bytes.
- Synthetic runtime E2E covers secure capture of three originals → analysis → review → action → outcome capture → recovery → Proof Pack → confidential offline export → independent verification.

## Current repository truth

Branch: `apps/industrial-claims`
PR: `#785` (DRAFT; do not merge)
Known head before this state update: `e376f25263132341630749ed46f59fdc6d6b7a8b`

The last validated pre-rename test run had CausLedger/Certactum scope passing; the repository remained globally red because of an unrelated Chile MercadoPublico temporal test. That unrelated Chile code/test is out of scope and must not be modified by this Factory.

This file update itself creates a newer branch HEAD. Exact-head CI must be checked before making a new green claim.

## Commercial / production truth

The technical workflow is advanced enough for continued pilot-readiness work, but the following must **not** be claimed without fresh external evidence:

- production-ready or fully deployed Certactum application;
- production WORM/TSA/HSM or equivalent provider configuration;
- independently verified real-customer secure intake;
- paid Certactum audit;
- recovered customer money;
- pilot validation;
- SaaS self-service completion.

The professional identity `marcos@certactum.com` has demonstrated mail delivery in the connected mailbox. Delivery/forwarding evidence is not equivalent to a complete high-volume sending/reputation assessment.

## Runtime/public surfaces

Certactum-related Vercel projects exist, including an outreach hub with a READY production deployment. This does not by itself prove that the complete customer application is deployed under one canonical production project/domain.

## Release gates

No real customer documentary data may be introduced until the secure production intake/storage/access-control path is genuinely configured and verified.

Do not fabricate provider receipts, WORM/HSM/TSA evidence, seals, signatures, public anchors, customer validation, payments, or recoveries.

Keep PR #785 DRAFT. No merge/deploy/production action from this Factory without an explicit production decision and satisfied operational controls.

## Active execution order

1. Complete the CausLedger → Certactum identity migration without breaking historical/evidence compatibility.
2. Re-run/inspect exact-head CI after each material migration tranche; never modify the unrelated Chile temporal failure.
3. Consolidate the canonical customer-facing Certactum web/runtime and eliminate stale public naming.
4. Verify domain/mail authentication and outbound readiness separately from simple delivery/forwarding.
5. Close production secure-intake/storage/access-control prerequisites.
6. Exercise a bounded authorized pilot only after those controls are real.
7. Convert first qualified case into a paid assisted audit and documented outcome.

## Non-negotiable truth boundary

A green synthetic test is evidence of implementation behavior, not evidence of a real customer, real entitlement, legal enforceability, production security, or recovered money.
