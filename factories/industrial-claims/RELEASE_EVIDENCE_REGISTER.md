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
- CLOSED — Vercel canonical project `changeclaim` currently has a READY production deployment.
- CLOSED — Canonical Vercel project currently carries both `certactum.com` and `www.certactum.com` domains.
- VERIFIED 2026-09-03 — `https://certactum.com` permanently redirects to `https://www.certactum.com/`; the canonical `www` endpoint returned HTTP 200 through the connected Vercel fetch.
- VERIFIED 2026-09-03 — Production shell fetch confirms the Certactum root remains a lightweight Vercel loader for the external application document; Vercel READY is not being confused with full customer-journey proof.
- VERIFIED 2026-09-03 — Connected Neon project `certactum-core` is accessible; schema includes organizations, projects, memberships, changes, notices, decisions, evidence, audit log and evidence upload token tables.
- VERIFIED 2026-09-03 — Current production data counts are 1 organization, 1 project, 1 membership, 2 change records and 0 evidence records. No real confidential evidence is present in the evidence table at this checkpoint.
- EXTERNAL PENDING — Production backup schedule, off-site/independent copy, restore drill and RPO/RTO evidence.
- EXTERNAL PENDING — Independent external uptime/error alert delivery verification beyond platform runtime inspection.

## Commercial/support journey
- CLOSED — Public commercial identity uses marcos@certactum.com.
- CLOSED — Help instructs users not to send confidential documents by email without an authorized intake channel.
- CLOSED — Customer-zero abuse journey covers creation, cross-tenant denial, review segregation and internal action without implying external claim submission.
- INTERNAL CLOSED — Stripe integration direction is hosted Checkout; billing projection covers checkout completion, invoice paid activation, failed renewal/past-due, recovery, cancellation and refund.
- INTERNAL CLOSED — Billing event application is idempotent; event-ID semantic collision and missing Certactum account metadata fail closed.
- VERIFIED 2026-09-03 — Connected Stripe TEST Checkout completed a symbolic EUR 1.00 card payment (`pi_3UBZarABxblxoGAb1vRU1IIf`) with Certactum validation metadata.
- VERIFIED 2026-09-03 — TEST-mode full refund of that EUR 1.00 payment succeeded (`re_3UBZarABxblxoGAb1CYZGmsx`), proving Stripe refund execution without touching live funds.
- VERIFIED 2026-09-03 — Connected Stripe LIVE Checkout completed a symbolic EUR 1.00 card payment (`pi_3UBZtEABxblxoGAb1Oa3kP8V`), amount received EUR 1.00, status `succeeded`, metadata purpose `symbolic_live_validation`, statement descriptor suffix `CERTACTUM`.
- TRUTH BOUNDARY — The LIVE EUR 1.00 transaction is a technical validation payment, not a commercial customer, subscription, sale validation or recovered revenue. It remains intentionally unrefunded at the owner's instruction because refunding it provides no additional live-flow evidence beyond the successful TEST refund.
- PENDING — Final commercial price/plan and corresponding recurring subscription lifecycle exercise, including failed renewal and recovery against the final commercial configuration.
- PENDING — Final browser-visible onboarding walkthrough from fresh account to first verified dossier must be recorded against the canonical deployed application. This cannot be marked CLOSED from HTTP/DB inspection alone.

## Security/legal truth boundary
- CLOSED — No internal gate claims court acceptance, certification, liability or guaranteed recovery.
- CLOSED — No real customer documentary data is authorized before production identity/storage/access controls are verified.
- EXTERNAL PENDING — Independent pentest and remediation evidence.
- EXTERNAL PENDING — GDPR controller/processor mapping, DPA/privacy/retention/incident procedures reviewed for production use.
- EXTERNAL PENDING — Jurisdiction-specific legal review of evidentiary positioning.

## CI truth
- VERIFIED 2026-09-03 — Exact-head validation for commit `6fae35f4e2537eb534382616d0868faf6eb36734`, workflow run `33683326028`: Mobile SUCCESS; Python repository/Factory Cloud suite `1310 passed, 2 skipped, 2 warnings, 1 failed`.
- The sole failure at that exact head is the unrelated Chile MercadoPublico assertion `tests/test_chile_mercadopublico.py::test_observation_uses_visible_amount_only_and_preserves_publisher_state`, expecting `is_actionable=True` while receiving `False`.
- No Certactum-caused failure was observed in that exact-head run. The global workflow conclusion remains FAILURE solely because the unrelated Chile test is part of the repository-wide job; do not relabel the global workflow as green.
- This register update is documentary only; it does not change executable Certactum code. Any later executable-code head must receive its own exact-head validation.

## Launch decision rule
Internal launch readiness can be declared only when every non-external PENDING line above is CLOSED with evidence and exact-head Certactum tests show no Certactum-caused failure. External certification/trust upgrades can follow revenue where explicitly accepted, but production identity, access control, storage and data-handling controls cannot be bypassed for real confidential customer evidence.
