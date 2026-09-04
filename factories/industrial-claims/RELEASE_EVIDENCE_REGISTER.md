# VINDORUM — RELEASE EVIDENCE REGISTER

This register is the VINDORUM launch gate. A control is CLOSED only when VINDORUM-specific evidence exists. Evidence from any other project does not count.

## Identity
- CLOSED — Canonical company/product identity is VINDORUM in the active Factory contract, public surface and zero-touch product journey.
- CLOSED — Dedicated billing namespace is VINDORUM-only.
- CLOSED — Cross-project identity reuse is blocked by automated regression tests.
- PENDING — Dedicated production domain selected and controlled by VINDORUM.
- PENDING — Dedicated VINDORUM sender mailbox and sender authentication proven.

## Customer journey
- CLOSED — Free Exposure Check is metadata-only and does not require a meeting.
- CLOSED — Normal journey is modeled with `operator_intervention_required=false`.
- CLOSED — Browser/client checkout success alone cannot unlock paid product state.
- CLOSED — Evidence gaps fail closed rather than being promoted to claims.
- CLOSED — Dossier/reconciliation preserve documented → supported → claimed → approved → settled truth.
- PENDING — Browser-visible production E2E from fresh user through first delivered dossier.

## Confidential evidence intake
- CLOSED — Product contract blocks confidential intake until readiness is genuinely green.
- CLOSED — WORM and timestamp provider declarations are distinct from certification/court acceptance.
- PENDING — Production IdP/MFA/account recovery evidence.
- PENDING — Secure tenant/case-bound transfer exercised in production.
- PENDING — WORM/Object Lock provider configured, probed and receipted.
- PENDING — Trusted timestamp provider configured, probed and receipted.
- PENDING — Retention/deletion and privacy/DPA procedures approved for production.
- PENDING — Incident handling and independent security/pentest evidence appropriate to production use.

Until all blocking controls are satisfied, `real_evidence_intake_enabled` must remain false.

## Proof architecture
- CLOSED — Append-only reconciliation history, deterministic reconciliation hashes and fail-closed economic invariants exist.
- CLOSED — Current-revision/latest-reconciliation portfolio rules exist.
- CLOSED — Proof architecture explicitly distinguishes integrity/time/source authentication from factual truth and legal recoverability.
- PENDING — External proof providers exercised end-to-end with VINDORUM production receipts.

## Billing
- CLOSED — VINDORUM billing state/event namespace is isolated from other products.
- CLOSED — Paid-state activation requires verified payment evidence.
- PENDING — Final VINDORUM merchant/Stripe production configuration proven.
- PENDING — Final commercial price lifecycle tested end-to-end against the production configuration.
- PENDING — Real VINDORUM customer payment. Test/symbolic payments from any other project do not count.

## Deployment
- CLOSED — Isolated static deployment package and security headers exist in `vertical_apps/industrial_claims/public_site`.
- CLOSED — Package forbids cross-project identity and confidential upload on the pre-production public surface.
- PENDING — Dedicated VINDORUM Vercel project created and verified.
- PENDING — Production hostname/browser smoke test for the dedicated VINDORUM deployment.

No deployment, domain or runtime belonging to another company can satisfy these gates.

## Commercial proof
- CLOSED — REAL and TEST commercial proof classes are separated.
- CLOSED — Opens/clicks/synthetic activity cannot advance real commercial state.
- CLOSED — Ten named buyer research targets and corporate routes exist as research hypotheses only.
- PENDING — Dedicated VINDORUM sender ready and authorized outbound sent.
- PENDING — Real metadata-qualified buyer.
- PENDING — Bounded real case confirmed.
- PENDING — Verified paid Recovery Scan/audit commitment.
- PENDING — Verified case outcome.
- PENDING — Real VINDORUM customer payment and repeat/monitoring signal.

## CI
- ACTIVE — PR #955 must pass Python + Mobile on the exact immutable head after the complete VINDORUM identity/zero-touch migration.
- No earlier green run is reused after the head changes.

## Launch rule
VINDORUM may expose the metadata-only Free Exposure Check before confidential intake is production-ready, provided the public surface stays truthful and does not accept confidential documents or pretend live payment/intake capabilities.

Confidential evidence intake, paid-access unlock and production dossier delivery require their actual VINDORUM-specific gates. Nothing from another project can be substituted as proof.
