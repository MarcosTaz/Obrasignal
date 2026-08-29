# Factory Cloud Shared Capability Gate Audit v0.2

Status: INDEPENDENT_SAFETY_AUDIT / NON_RUNTIME / CRITICAL_FINDINGS_OPEN / NO_MERGE_AUTHORIZATION

## Scope

This audit evaluates Factory Cloud PR #760 against the Side Factory G1–G5 gates and Empire Blast-Radius Rule.

Observed shared owner:
- repository `MarcosTaz/Obrasignal`
- PR #760
- branch `factory-cloud/shared-platform-portfolio-architecture`
- observed exact HEAD `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head Quality run `33265278871`: SUCCESS

Additional source evidence:
- Industrial Claims `apps/industrial-claims@449e3e846d1ad7096b7cf6790ecc119299a35023`, Quality `33270696084`: SUCCESS
- Aviation canonical `apps/aviation-lease-entitlement-recovery@0d1759832a06b3177b67b35a4c53ee0c69db459e`
- ContractCredit canonical `apps/contractcredit@0d1759832a06b3177b67b35a4c53ee0c69db459e`

Green source/tests prove only the behavior actually exercised. They do not upgrade synthetic references into documentary evidence or a local-head check into remote source truth.

## Promotion scale

- `PASS_GLOBAL_CONTRACT`: domain-neutral contract/source primitive proven across real consumers.
- `PASS_RECOVERY_KERNEL_SCOPE`: shared within recovery/economic-assurance family only.
- `PASS_WITH_AUTHORITY_BOUNDARY`: shared representation/source is acceptable while production/provider authority remains consumer-owned.
- `PARTIAL`: implementation exists but a required runtime/evidence/lifecycle proof is incomplete.
- `FAIL`: current source contradicts the stronger claimed state or creates unsafe truth.

## Current independent gate matrix

| Capability | Independent disposition | Material boundary |
|---|---|---|
| tenant/role context | PASS_WITH_AUTHORITY_BOUNDARY | shared context != shared identity provider |
| identity principal contract | PASS_WITH_AUTHORITY_BOUNDARY | token/provider authority consumer-owned |
| entitlement snapshot | PASS_WITH_AUTHORITY_BOUNDARY | merchant/billing mutation consumer-owned |
| EvidenceEnvelope / evidence lineage | PASS_GLOBAL_CONTRACT | evidence container != evidence sufficiency policy |
| notification/outbox contract | PASS_WITH_AUTHORITY_BOUNDARY | delivery credentials/provider consumer-owned |
| deterministic calculation contract | PASS_RECOVERY_KERNEL_SCOPE | formula/applicability remains vertical-owned |
| deadline window | PASS_RECOVERY_KERNEL_SCOPE | date state != legal deadline authority |
| finding record/state model | PASS_RECOVERY_KERNEL_SCOPE / LIFECYCLE_PARTIAL | recovery vocabulary not global; outcome path currently under-evidenced |
| audit event primitive/storage | PASS_GLOBAL_CONTRACT | deterministic tenant-scoped event primitive proven |
| **full review -> action -> outcome audit lineage** | **PARTIAL / NOT PROVEN ON AVIATION+CONTRACTCREDIT CANONICAL PATHS** | current shared ops omits transition audits/actors |
| ReleaseEvidence exact-SHA contract | PASS_GLOBAL_CONTRACT | concrete repository workflow remains local |
| source_truth_verification library | PASS_LIBRARY / RUNTIME_INTEGRATION_PARTIAL | live remote check not wired into real persistent worker path |
| persistent_execution_recovery | SHARED_CONTRACT_PROPOSED | real supervised runtime consumers not proven |
| exact duplicate fingerprint detection | SHARED_VERIFIED_EXACT_DUPLICATE | semantic/economic overlap policy not proven |
| fee calculation lineage | SHARED_VERIFIED_CALCULATION_LINEAGE | contractual fee entitlement not proven; depends on sound outcome |
| entitlement basis representation | SHARED_VERIFIED_REPRESENTATION | contractual entitlement determination remains vertical-owned |
| raw DocumentStore component | REUSABLE_SOURCE_COMPONENT | multi-vertical runtime adoption not proven |
| backup/restore utility | REUSE_PROVEN_RECOVERY_VERTICALS | operational backup authority app-owned |

## Critical finding 1 — source-truth verification overpromotion

Factory Cloud contains a sound `GitHubHeadVerifier` / `VerifiedDispatchAdapter` library: live branch mismatch, unavailable provider or missing source truth fail closed.

The real persistent worker path, however, instantiates `ProcessAgentAdapter` directly and verifies only local workspace HEAD against the registry-pinned HEAD before running the app agent. Runtime provisioning/gate logic also proves the local workspace, not the live remote branch immediately before execution.

Current evidence makes this concrete: PR #760 pins Industrial Claims at `529debe635aa281b0c6062a2de7f6ef580e57738`, while live `apps/industrial-claims` is `449e3e846d1ad7096b7cf6790ecc119299a35023`, 131 commits ahead and GREEN.

Independent disposition:

`SHARED_VERIFIER_LIBRARY_PROVEN / REAL_WORKER_REMOTE_HEAD_INTEGRATION_PARTIAL`.

Owner repair contract is recorded on PR #760 comment `5464440957`.

Required proof:
1. live remote-head verification is mandatory in the actual worker/pre-dispatch path;
2. remote unavailable => WAIT/UNKNOWN;
3. branch mismatch => block before app agent execution;
4. stale registry + stale matching local workspace + newer remote branch => delegate/agent call count zero;
5. only then refresh registry exact heads.

## Critical finding 2 — evidence-backed entitlement is not proven for Aviation/ContractCredit

Canonical Aviation and ContractCredit sources still synthesize EvidenceEnvelope content from identifiers and economic inputs, then hardcode a rule reference and `SUPPORTED` confidence.

Examples from current shared vertical consumers include internally generated content equivalent to:
- `lease:{contract_ref}`;
- `maintenance:{event_ref}:{eligible_cost}`;
- `service-contract:{contract_ref}`;
- `incident:{incident_ref}:{monthly_fee}:{credit_rate}`.

Current canonical web `/analyze` paths accept references, numeric inputs and dates; they have no route for the real executed clause/remedy evidence required to justify those entitlement claims.

Therefore:

`EVIDENCE ENVELOPE EXISTS != CONTRACTUAL EVIDENCE EXISTS`.

`RULE_REF EXISTS != RULE APPLIES`.

`SUPPORTED != SAFE` when support is manufactured from caller references rather than documentary evidence.

Independent disposition for current Aviation/ContractCredit app paths:

`ENGINEERING_SYNTHETIC_FLOW_GREEN / REAL ENTITLEMENT EVIDENCE INTEGRITY FAIL`.

Critical owner repair contract is on PR #760 comment `5464535076` and detailed in `RECOVERY_ENTITLEMENT_OUTCOME_INTEGRITY_AUDIT_V01.md`.

## Critical finding 3 — RECOVERED outcome is too weak on current Aviation/ContractCredit path

Canonical shared `AssuranceOperations` used by Aviation/ContractCredit currently allows:
- review state mutation without audit event;
- action without actor/audit;
- resolve from any nonnegative decimal amount + arbitrary non-empty currency/evidence-ref string;
- no persisted/verified outcome EvidenceEnvelope requirement;
- no cap against reviewed calculation/potential;
- no currency reconciliation to reviewed calculation;
- no resolution audit.

A positive caller-supplied amount therefore creates `RECOVERED` even though real recovery evidence and economic reconciliation have not been established by the current shared path.

Independent disposition:

`RECOVERY STATE MACHINE SOURCE EXISTS / EVIDENCE-BACKED OUTCOME LIFECYCLE PARTIAL`.

This downgrades the previous stronger interpretation of `audit_decision_lineage=SHARED_CORE`: the **audit primitive** is proven, but the **full recovery lifecycle audit** is not.

## Stronger compatible implementation already exists

Industrial Claims current GREEN branch demonstrates a reusable direction without centralizing Industrial semantics:
- missing commercial/event/cost content remains `REFERENCE_ONLY` and cannot make entitlement actionable;
- reviewed calculation + currency are loaded before outcome;
- recovery above reviewed maximum fails closed and requires amendment/re-review;
- currency mismatch fails closed;
- actual outcome evidence content is persisted as EvidenceEnvelope;
- evidence + outcome can be committed atomically;
- newer shared `assurance_ops.py` adds actor-aware review/action/resolve audits and transaction-capable resolve;
- fee duplication per outcome is tightened.

Architecture rule:

`REUSE NEUTRAL TRANSITION/EVIDENCE MACHINERY`
+
`KEEP ENTITLEMENT / MAXIMUM / APPLICABILITY RULES VERTICAL-OWNED`.

## Capability-specific safe states

### EvidenceEnvelope

G1–G5 remain PASS at the contract/source layer. Aviation, ContractCredit and Industrial Claims all consume it.

The primitive is neutral, but each vertical must decide what evidence is sufficient and must not manufacture documentary support from identifiers.

Disposition: `PASS_GLOBAL_CONTRACT`.

### Deterministic calculation

The shared reproducibility contract remains valid. A deterministic formula can still compute from unsupported inputs, so calculation reproducibility must never be interpreted as entitlement validity.

Disposition: `PASS_RECOVERY_KERNEL_SCOPE`.

### Deadline window

Evidence-linked date tracking is reusable. Jurisdiction/business calendar/tolling/notice meaning remains vertical-owned.

Disposition: `PASS_RECOVERY_KERNEL_SCOPE`.

### Finding workflow

The data/state vocabulary is reusable inside recovery assurance. Current Aviation/ContractCredit transition implementation does not prove evidence-backed `RECOVERED` or complete audit lineage.

Disposition: `PASS_RECOVERY_KERNEL_RECORD / OUTCOME_LIFECYCLE_PARTIAL`.

### Audit lineage

`AuditEvent` itself remains a good tenant-scoped deterministic primitive and storage path.

Current strongest safe statement:

`AUDIT EVENT PRIMITIVE = SHARED_PROVEN`

not:

`EVERY MATERIAL RECOVERY DECISION/TRANSITION = AUDITED`.

### Fee lineage

Fee arithmetic lineage remains deterministic, but:
- contractual fee terms are external/vertical/customer authority;
- an under-evidenced RECOVERED outcome cannot safely support a success-fee claim.

Disposition: `FEE_CALCULATION_LINEAGE_PROVEN / FEE ENTITLEMENT AND OUTCOME BASIS EXTERNAL`.

## Product Checker and K3 boundary

No recovery-kernel gate in this document assumes K3 or Product Checker are consumers.

- K3: runtime proven; canonical editable source unknown.
- Product Market Access / Legal Product Checker: switchboard/business Factory exists, but canonical application source/runtime is not established and Factory Cloud app registration excludes it.

Recovery-family reuse is not universal-product proof.

## Owner actions

### Factory Cloud PR #760

1. Repair live remote source-head verification in the real persistent worker path.
2. Reconcile the neutral actor/audit/transaction improvements already proven in Industrial Claims.
3. Require verticals to supply and validate real contractual/event evidence before `SUPPORTED`/`READY_FOR_REVIEW`.
4. Require verified outcome evidence before `RECOVERED`.
5. Reconcile outcome amount/currency to reviewed vertical-owned truth or force amendment/re-review.
6. Keep `persistent_execution_recovery` below SHARED_VERIFIED until supervised runtime proof exists.
7. Keep auth/billing provider authority and production data boundaries consumer-owned.

### OS Side Factory PR #608

1. remain non-runtime;
2. track owner fixes at exact heads;
3. do not duplicate the shared implementation;
4. re-audit all stronger promotion/maturity labels after owner repair;
5. preserve K3/Product Checker UNKNOWN boundaries.

## ACTIVE / NEXT / WAIT

ACTIVE: block false entitlement/recovery maturity for Aviation and ContractCredit; track owner reconciliation of Industrial-proven neutral safety machinery and the source-verifier worker repair.

NEXT: recheck PR #760 exact HEAD for repairs; verify canonical Aviation/ContractCredit heads after any owner movement; re-run G1–G5 and real-customer pilot readiness only from repaired exact-head evidence.

WAIT: evidence-complete real-customer pilot-capable classification for Aviation/ContractCredit, success-fee reliance, source-verifier SHARED_VERIFIED runtime status, supervised persistent runtime, K3 source resolution, Product Checker app source/runtime, merge, deploy, production data/secrets/auth/billing/database authority.
