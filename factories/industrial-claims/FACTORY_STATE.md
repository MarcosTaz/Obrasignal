# INDUSTRIAL SUPPLIER CLAIMS & MARGIN RECOVERY / CAUSLEDGER — FACTORY STATE

## MISSION
Build an evidence-first supplier-side industrial commercial recovery product that reconstructs documented recovery candidates, preserves uncertainty, requires independent human review, records only documented final cumulative outcomes, and never invents entitlement, legal recoverability, external authority, or recovered cash.

## SOURCE TRUTH
- Repository: `MarcosTaz/Obrasignal`
- Application branch: `apps/industrial-claims`
- Draft PR: `#785`
- Last exact application-source GREEN: `6e59d0f9ac440b9fd16d758bb81697e487796fe5`
- Verification evidence: `ObraSignal Quality #4179`, run `33286344803`; Python SUCCESS; Mobile SUCCESS.
- Factory Cloud source/provisioning pointers intentionally reference that exact GREEN source snapshot.
- Metadata/state commits after the source snapshot do not upgrade the application source and require their own exact-head CI before the branch itself is described as GREEN.

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
- Tenant-scoped reviewer/operator queue and tenant-safe detailed dossier endpoint.
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
- Exact application-source GREEN: `6e59d0f9ac440b9fd16d758bb81697e487796fe5`.
- CI: ObraSignal Quality #4179 / run 33286344803.
- Industrial allowlisted suite includes service, recovery cap, replay, atomic persistence, case metadata atomicity, outcome atomicity, document privacy, input bounds, collision resistance, synthetic oracle, package, pilot contract, backup/restore, web, HTTP intake, console, queue, finding detail and dossier integrity tests, plus shared recovery contracts.
- Known code regressions at source snapshot: none.

## ACTIVE
Continue repository-only P0/P1 hardening from the exact GREEN source snapshot. Current focus: make duplicate/replay validation transactionally atomic so a later replay conflict cannot leave partial repair/orphan rows if durable state was already incomplete or externally corrupted.

## NEXT
1. Add replay rollback regression and atomic replay validation.
2. Exact-head CI after the replay hardening.
3. Repin Factory Cloud source/provisioning only after the new exact source snapshot is GREEN.
4. Final Industrial P0/P1 scan: identity/tenant leakage, raw-content leakage, truth-language overclaim, deadline semantics, outcome semantics, queue/detail dead ends, unsafe HTTP failures, replay/atomicity, pricing/commercial overclaim.
5. Repair every executable finding and re-run exact-head CI.
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
Read `apps/industrial-claims` exact HEAD, complete atomic replay validation + rollback regression, fetch the exact ObraSignal Quality run, repair any failure immediately, then continue the P0/P1 scan. Never reset to an older plan or treat a GREEN milestone as Factory completion.
