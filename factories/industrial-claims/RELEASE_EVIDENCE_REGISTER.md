# CERTACTUM — RELEASE EVIDENCE REGISTER

This register is the internal launch gate. A control is only CLOSED when evidence exists. External controls remain PENDING until third-party evidence exists.

## Product identity and UX
- CLOSED — Canonical public/product identity is Certactum on current customer-facing public site, operator console and change-capture page.
- CLOSED — Approved visual language preserved; hardening changes do not redesign the visual system.
- CLOSED — Console queue auto-loads; selected dossier persists within the browser session; duplicate form submission is blocked while a request is in flight; explicit scroll restoration avoids refresh jumps.
- CLOSED — Responsive CSS already provides one-column layouts for tablet/mobile breakpoints on current console/public surfaces.
- CLOSED — Customer Help exists in PT, EN, FR and ES.
- PENDING — Approved final logo/favicon asset must be visually verified against the canonical production deployment; do not fabricate or silently replace an asset.

## Identity and authorization
- CLOSED — Tenant comes from verified identity context, not request body.
- CLOSED — JWT tenant claim can be configured separately from user subject and fails closed when required but missing/invalid.
- CLOSED — Role separation covers analyst/reviewer/operator; cross-role abuse fails closed.
- CLOSED — X-Tenant-ID and X-Actor-ID spoof attempts fail closed.
- CLOSED — Customer-zero adversarial test verifies cross-tenant dossier/proof access is denied.
- EXTERNAL PENDING — Production IdP configuration and privileged MFA.
- EXTERNAL PENDING — Account recovery exercise with real production identities.

## Evidence custody and proof
- CLOSED — Secure capture is authorization-scoped, actor-bound and replay-bound.
- CLOSED — Source authentication remains UNVERIFIED unless independently established.
- CLOSED — Immutable provider contract requires COMPLIANCE retention, exact-version readback and digest/length verification.
- CLOSED — Semantic rebinding/collision attempts fail before duplicate immutable writes.
- CLOSED — Proof Pack/offline export binds exact originals and outcome evidence and independently rehashes them.
- CLOSED — E2E includes effective_at replay tampering and exact-original export validation.
- EXTERNAL PENDING — Production WORM/Object Lock provider and archived provider receipts.
- EXTERNAL PENDING — Real qualified/trusted timestamp provider and historical validation.

## Operational resilience
- CLOSED — Verified SQLite backup uses online backup API, integrity_check, SHA-256 receipt and atomic destination replacement.
- CLOSED — Restore requires expected SHA-256 and rejects a tampered backup before destination mutation.
- CLOSED — Secret-free readiness report distinguishes blocking failures, warnings and external proof dependencies.
- CLOSED — 200 repeated tenant-scoped queue reads smoke-test stable no-store behavior.
- CLOSED — Request size limits and secure intake byte limits are enforced by existing gates.
- CLOSED — Vercel canonical project `changeclaim` currently has a READY production deployment and no runtime-error clusters in the inspected 24-hour window.
- CLOSED — Canonical Vercel project currently carries both `certactum.com` and `www.certactum.com` domains.
- EXTERNAL PENDING — Production backup schedule, off-site/independent copy, restore drill and RPO/RTO evidence.
- EXTERNAL PENDING — Independent external uptime/error alert delivery verification beyond platform runtime-error inspection.

## Commercial/support journey
- CLOSED — Public commercial identity uses marcos@certactum.com.
- CLOSED — Help instructs users not to send confidential documents by email without an authorized intake channel.
- CLOSED — Customer-zero abuse journey covers creation, cross-tenant denial, review segregation and internal action without implying external claim submission.
- INTERNAL CLOSED — Stripe test-mode integration direction is hosted Checkout; billing projection covers checkout completion, invoice paid activation, failed renewal/past-due, recovery, cancellation and refund.
- INTERNAL CLOSED — Billing event application is idempotent; event-ID semantic collision and missing Certactum account metadata fail closed.
- PENDING — End-to-end Stripe-hosted Checkout session/webhook exercise against the connected test account after a final commercial price/plan is fixed; no live charge is required pre-launch.
- PENDING — Final onboarding walkthrough from fresh account to first verified dossier must be recorded against the canonical deployed application.

## Security/legal truth boundary
- CLOSED — No internal gate claims court acceptance, certification, liability or guaranteed recovery.
- CLOSED — No real customer documentary data is authorized before production identity/storage/access controls are verified.
- EXTERNAL PENDING — Independent pentest and remediation evidence.
- EXTERNAL PENDING — GDPR controller/processor mapping, DPA/privacy/retention/incident procedures reviewed for production use.
- EXTERNAL PENDING — Jurisdiction-specific legal review of evidentiary positioning.

## CI truth
- CLOSED — Exact-head validation for commit 6fae35f4e2537eb534382616d0868faf6eb36734 completed: 1310 passed, 2 skipped, 2 warnings; Mobile passed.
- The sole repository-wide failure remains `tests/test_chile_mercadopublico.py::test_observation_uses_visible_amount_only_and_preserves_publisher_state`, where an unrelated Chile MercadoPublico assertion expects `is_actionable=True` but receives `False`.
- No Certactum-caused failure was observed in that exact-head run. The global workflow conclusion remains FAILURE because the unrelated Chile test is part of the same repository-wide job; do not relabel the global workflow as green.

## Launch decision rule
Internal launch readiness can be declared only when every non-external PENDING line above is CLOSED with evidence and exact-head Certactum tests show no Certactum-caused failure. External certification/trust upgrades can follow revenue where explicitly accepted, but production identity, access control, storage and data-handling controls cannot be bypassed for real confidential customer evidence.
