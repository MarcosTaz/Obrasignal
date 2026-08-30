# INDUSTRIAL SUPPLIER CLAIMS & MARGIN RECOVERY / CAUSLEDGER — FACTORY STATE

## MISSION
Build an evidence-first supplier-side industrial commercial recovery product that reconstructs documented recovery candidates, preserves uncertainty, requires independent human review, supports auditable correction/supersession of pre-action reconstructions, records only documented final cumulative outcomes, and never invents entitlement, legal recoverability, external authority, or recovered cash.

## SOURCE TRUTH
- Repository: `MarcosTaz/Obrasignal`
- Application branch: `apps/industrial-claims`
- Draft PR: `#785`
- Last exact application-source GREEN: `fccd959ab92fad297970bc7481ce92b90672c2ad`
- Verification evidence: `ObraSignal Quality #4314`, run `33329594415`; exact-head SUCCESS.
- Factory Cloud registry and runtime-provisioning contract point to that exact GREEN application snapshot.
- Pointer/state metadata commits after that source snapshot require their own exact-head CI before the branch HEAD itself is described as GREEN.

## DONE
- Tenant-safe verified-provider identity boundary; raw tenant/actor headers are assertions only.
- Role separation: analyst / reviewer / operator / admin with four-eyes self-review prohibition.
- Evidence-first intake: references alone remain unresolved; supplied documentary contents are hashed; raw source/outcome contents are not persisted.
- Explicit currency lineage with no implicit conversion.
- Numeric finite/non-negative/capacity validation and exact Decimal working precision.
- Immutable reviewed net-potential recovery cap.
- Structured recovery fingerprint and fingerprint-scoped internal case/evidence IDs prevent delimiter and reused-human-reference collisions.
- Durable case metadata, recovery index, revision lineage and shared case persistence are transactionally protected.
- Replay integrity prevents economic/currency/evidence/metadata rewrite, lifecycle downgrade and partial replay repair on late conflict.
- Pre-review entitlement truth remains non-actionable: documentary-complete = PARTIAL; missing evidence = UNRESOLVED.
- Notice truth is analyst-declared (`DECLARED_DATE_FOR_REVIEW` / `DECLARED_NONE_FOR_REVIEW`) or UNKNOWN; deadline timing OPEN / DUE_TODAY / EXPIRED is operational risk only.
- Dossier read model fails closed on corrupt/ambiguous evidence, calculation, deadline, entitlement, fingerprint, audit and outcome lineage.
- Review/action/resolve require a valid current revision before mutation.
- `APPROVED` and `ACTIONED` are internal workflow states only and confer no customer/external authority.
- Resolve requires explicit final-cumulative confirmation, matching reviewed currency, documentary outcome evidence and reviewed-value cap.
- Tenant-scoped reviewer/operator queue exposes only current revisions; historical revisions remain readable through detail.
- Amendment/revision workflow implemented: one logical recovery fingerprint across revisions; immutable identity fields; analyst-only correction; fresh independent review; superseded revisions remain historical and transition-ineligible; amendment blocked after ACTIONED/final outcome; supersession persists atomically; old-revision replay fails closed.
- Amendment HTTP boundary is tenant-scoped and role-gated.
- Console provides safe amendment mode using full corrected intake; raw documents are never reloaded from storage.
- Backup/restore preserves revision history, current pointer, full dossier lineage, tenant isolation and raw-content absence.
- Browser shell uses CSP/no-store/nosniff/no-referrer/restrictive permissions and safe DOM APIs; no `innerHTML`.
- Input bounds and control-character defenses cover tenant/refs/IDs/actors/reasons/missing-evidence and pathological decimals.
- Factory Cloud Industrial allowlist includes revision-store, amendment domain, amendment HTTP, revision backup/restore and console-amendment regressions.
- Pilot contract schema v14 explicitly encodes amendment, supersession, fresh-review, backup, evidence, transition, security and commercial-truth constraints.

## PRODUCT TRUTH
- `READY_FOR_REVIEW` = documentary candidate ready for independent human review only.
- `CONTENT_HASHED` = content supplied and hash provenance recorded; not authenticity, legal sufficiency or contractual support.
- `PARTIAL` pre-review entitlement confidence is not an approved entitlement.
- `APPROVED` = internal workflow approval only.
- `ACTIONED` = internal workflow state only; no customer action is performed by this repository flow.
- An amendment is a correction/supersession of the same logical recovery, not a new recovery and not customer/external action.
- Every amendment requires a new full corrected documentary reconstruction and fresh independent review; raw documents are not rehydrated from storage.
- Superseded revisions remain audit-readable but cannot be reviewed, actioned or resolved.
- `RECOVERED` / `CLOSED_NO_RECOVERY` records a documented final cumulative outcome under the current single-close model.
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
- Exact application-source GREEN: `fccd959ab92fad297970bc7481ce92b90672c2ad`.
- CI: ObraSignal Quality #4314 / run `33329594415` SUCCESS.
- Preceding regression CI #4310 failed only on revision-detail field naming; 1010 tests passed and Mobile passed. Tests were aligned to the established `revision.number` contract and exact-head #4314 passed.
- Industrial allowlisted suite includes shared recovery contracts plus service, recovery cap, replay, atomic persistence, case metadata, revision store, amendment, amendment HTTP, outcome atomicity, document privacy, input bounds, collision resistance, synthetic oracle, package, pilot contract, full backup/restore, revision backup/restore, web, HTTP intake, console, console amendment, queue, detail and dossier-integrity tests.
- Known code regressions at exact GREEN source snapshot: none.

## ACTIVE
Continue repository-only P0/P1 scan from exact GREEN source `fccd959ab92fad297970bc7481ce92b90672c2ad`. Current highest-value candidate: revision resumability — historical detail should expose the current/successor finding so a stale client can recover after supersession without guessing.

## NEXT
1. Prove the revision-resumability gap with a failing-before regression.
2. Expose tenant-safe current/successor revision navigation without changing recovery identity or making amendment implicitly idempotent.
3. Run exact-head CI; repair any regression immediately.
4. Repin Factory Cloud only to a newer exact-head GREEN source snapshot if source code changes.
5. Continue final P0/P1 scan for tenant/raw-content leakage, truth-language overclaim, lifecycle dead ends, collision semantics, unsafe HTTP failures, replay/atomicity and commercial overclaim.
6. Keep runtime, provider, market, legal, customer and production authority items in WAIT.

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
Read `apps/industrial-claims` exact HEAD and exact-head CI. Resume revision-resumability P1 first. If the branch moved or CI failed, repair the exact current regression before further work. Never reset to an older plan or treat a GREEN milestone as Factory completion.
