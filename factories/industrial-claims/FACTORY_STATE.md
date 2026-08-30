# INDUSTRIAL SUPPLIER CLAIMS & MARGIN RECOVERY / CAUSLEDGER — FACTORY STATE

## MISSION
Build an evidence-first supplier-side industrial commercial recovery product that reconstructs documented recovery candidates, preserves uncertainty, requires independent human review, records only documented final cumulative outcomes, and never invents entitlement, legal recoverability, external authority, or recovered cash.

## SOURCE TRUTH
- Repository: `MarcosTaz/Obrasignal`
- Application branch: `apps/industrial-claims`
- Draft PR: `#785`
- Last exact application-source GREEN: `c6de16e5a23483bb27ef33f6abf329752bde45bb`
- Verification evidence: ObraSignal Quality run `33287246832`; exact-head SUCCESS.
- Current source milestone includes revision-aware queue/detail proof and atomic replay rollback protection.
- This BATON update is metadata/state only; the new branch HEAD created by this edit requires its own CI before the branch HEAD itself is described as GREEN.

## DONE
- Tenant-safe provider identity boundary; raw tenant/actor headers are assertions only, not authority.
- Role separation: analyst / reviewer / operator / admin with four-eyes self-review prohibition.
- Evidence-first intake: reference-only sources remain unresolved; supplied source contents are hashed; raw documentary contents are not persisted.
- Explicit currency lineage with no implicit conversion.
- Numeric finite/non-negative/capacity validation and exact Decimal working precision.
- Immutable recovery cap against reviewed net potential.
- Structured recovery fingerprint prevents delimiter collisions.
- Internal case IDs derive from the recovery fingerprint so distinct contracts can share event/family references without collision.
- Shared-store outcome IDs are tenant-scoped.
- Durable Industrial case metadata is atomic with recovery index/shared case persistence.
- Replay integrity prevents economic, currency, evidence, and metadata rewrites.
- Duplicate/replay validation is transactionally atomic: a late immutable audit collision cannot leave an earlier replay repair committed; regression coverage proves missing evidence remains missing after rollback.
- Pre-review entitlement truth is deliberately non-actionable: documentary-complete = PARTIAL; missing evidence = UNRESOLVED.
- Notice values are analyst declarations (`DECLARED_DATE_FOR_REVIEW` / `DECLARED_NONE_FOR_REVIEW`) or UNKNOWN, never software-verified contractual conclusions.
- Deadline timing exposes OPEN / DUE_TODAY / EXPIRED as operational risk only; expiry does not establish non-recoverability.
- Reviewer/operator read model validates dossier lineage and fails closed on corruption or ambiguous creation audit lineage.
- Review/action/resolve perform dossier-integrity preflight before state mutation.
- `APPROVED` means internal workflow approval only; no legal conclusion, recoverability finding, customer-contact authority, or external-claim authority.
- `action` changes internal state only.
- HTTP `resolve` requires explicit `final_cumulative=true`; outcome is a final cumulative close, not installment accounting.
- Outcome evidence is content-hashed and persisted atomically with final state; raw content is not persisted.
- Full multi-tenant dossier backup/restore coverage includes metadata, recovery index, findings, audits, outcomes, and raw-content absence.
- Tenant-scoped reviewer/operator queue and tenant-safe detailed dossier endpoint are revision-aware and fail closed on inconsistent durable lineage.
- Console supports selected dossier inspection before workflow decision, safe DOM rendering, no `innerHTML`, CSP, no-store, nosniff, no-referrer, restrictive permissions.
- HTTP intake rejects non-object JSON, malformed JSON, oversized requests, invalid identities, invalid roles, invalid bounds, and unsafe economic inputs deterministically.
- Claim package schema v6 preserves pre-review/non-authority/timing truth, excludes raw documents, validates caller labels against immutable recovery identity, and fails closed on hybrid tenant/vertical/claim-family identity.
- Recovery-app registration tests validate registry ↔ provisioning synchronization rather than freezing stale historical SHAs.
- Pilot contract schema v11 encodes the current evidence, entitlement, review, timing, outcome, transition, collision, backup, security and commercial truth constraints.

## PRODUCT TRUTH
- `READY_FOR_REVIEW` = documentary candidate ready for independent human review only.
- `CONTENT_HASHED` = content supplied and hash provenance recorded; not authenticity, legal sufficiency, or contractual support.
- `PARTIAL` pre-review entitlement confidence is not an approved entitlement.
- `APPROVED` = internal workflow approval only.
- `ACTIONED` = internal workflow state only; no customer action is performed by this repository flow.
- `RECOVERED` / `CLOSED_NO_RECOVERY` records a documented final cumulative outcome under the current single-close model.
- Raw documentary source/outcome content is not persisted by the Industrial service.
- No currency conversion is implemented.
- Expired declared notice timing is an urgency signal requiring human exception/waiver analysis, not a recoverability conclusion.

## BUSINESS TRUTH
- Pricing status: `HYPOTHESIS`.
- Commercial success: `UNPROVEN`.
- Real incremental recovery: not proven.
- Real customer revenue: not proven.
- Market validation: not proven.
- Production authority: false.
- This Factory is NOT `MARKET_VALIDATED`, NOT `PILOT_VALIDATED`, NOT `PILOT_CAPABLE`, NOT `COMMERCIAL_READY`, and NOT production ready.

## TEST / EVIDENCE STATE
- Exact application-source GREEN: `c6de16e5a23483bb27ef33f6abf329752bde45bb`.
- CI: ObraSignal Quality run `33287246832` SUCCESS.
- Atomic replay evidence: `tests/test_industrial_claims_replay_integrity.py::test_replay_validation_rolls_back_partial_repairs_on_late_conflict` corrupts durable state, induces a late immutable audit collision, and proves the attempted earlier evidence repair is rolled back.
- Industrial allowlisted suite includes service, recovery cap, replay, atomic persistence, case metadata atomicity, outcome atomicity, document privacy, input bounds, collision resistance, synthetic oracle, package, pilot contract, backup/restore, web, HTTP intake, console, queue, finding detail and dossier integrity tests, plus shared recovery contracts.
- Known code regressions at exact GREEN source snapshot: none.

## ACTIVE
Continue the final repository-only P0/P1 scan from exact GREEN source `c6de16e5a23483bb27ef33f6abf329752bde45bb`. Prioritize identity/tenant leakage, raw-content leakage, truth-language overclaim, deadline semantics, outcome semantics, queue/detail dead ends, unsafe HTTP failures, replay/atomicity and pricing/commercial overclaim. Do not re-open atomic replay as unfinished unless new evidence disproves the current regression.

## NEXT
1. Inspect current exact source for one executable P0/P1 defect beyond the completed atomic-replay/revision-aware queue-detail milestones.
2. Add a failing-before regression for the highest-impact real defect found; if no executable defect is found, record the scan evidence rather than inventing one.
3. Repair only after the failing-before proves the defect.
4. Run exact-head CI and preserve failures literally.
5. Repin Factory Cloud source/provisioning only after a new source snapshot is exact-head GREEN and the pin itself is authorized by repository-safe policy.
6. Keep runtime/provisioning and external authority items in WAIT; do not fake completion.

## WAIT / OWNER-ONLY / EXTERNAL DEPENDENCIES
- Runtime workspace provisioning at `/srv/factory-cloud/apps/industrial-claims` and supervised worker.
- Verified real upstream provider/JWT tenant + organization + role mapping in the target runtime.
- Real browser authentication/session binding and authorized external runtime exposure.
- Production deploy, secrets/config activation, provider activation or other production mutation.
- Real customer data/use until authorized.
- Customer outreach or market exposure.
- Pricing/WTP validation.
- Legal/recoverability review for real claims.
- Real recovered cash and real customer revenue evidence.
- Merge approval for draft PR #785.

## BLOCKERS
No repository-only blocker is accepted as a stop condition. Runtime, market, legal, customer and production authority dependencies remain external WAIT and must not be bypassed by fabrication.

## RESUME_AT
Read `apps/industrial-claims` exact HEAD and the most recent exact-head CI. Continue the P0/P1 scan beyond the already-completed atomic replay and revision-aware queue/detail milestones. If a real executable defect is found, prove it failing-before, repair it, and rerun exact-head quality; otherwise persist scan evidence and rotate. Never reset to an older plan or treat a GREEN milestone as Factory completion.
