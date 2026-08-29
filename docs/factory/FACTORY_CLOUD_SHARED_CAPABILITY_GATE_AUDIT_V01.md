# Factory Cloud Shared Capability Gate Audit v0.1

Status: INDEPENDENT_SAFETY_AUDIT / NON_RUNTIME / NO_MERGE_AUTHORIZATION

## Scope

This audit evaluates the executable shared implementation owned by Factory Cloud PR #760 against the Side Factory G1–G5 promotion gates and the Empire Blast-Radius Rule.

Observed implementation source:
- repository: `MarcosTaz/Obrasignal`
- PR #760
- branch: `factory-cloud/shared-platform-portfolio-architecture`
- exact observed HEAD: `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head ObraSignal Quality run `33265278871`: SUCCESS

Additional consumer evidence:
- Industrial Claims PR #785 / branch `apps/industrial-claims`
- exact observed HEAD `449e3e846d1ad7096b7cf6790ecc119299a35023`
- exact-head ObraSignal Quality run `33270696084`: SUCCESS

This audit evaluates the proven contract/source boundary. It does not grant production deployment, credential, merchant, customer-data or database authority.

## Promotion scale used by this audit

- `PASS_GLOBAL_CONTRACT`: domain-neutral across the broad platform contract surface.
- `PASS_RECOVERY_KERNEL_SCOPE`: safe/shared only within the recovery/economic-assurance family; not a universal ObraSignal/K3/Product Checker semantic.
- `PASS_WITH_AUTHORITY_BOUNDARY`: shared data/source contract is acceptable only while provider/runtime authority remains product-owned.
- `PARTIAL`: useful implementation exists, but one or more G1–G5 or runtime-integration proofs are incomplete.
- `FAIL`: evidence contradicts the claimed promotion state or creates unacceptable blast radius.

## Gate matrix

| Capability | G1 | G2 | G3 | G4 | G5 | Independent disposition |
|---|---|---|---|---|---|---|
| `tenant_role_isolation` | PASS | PASS | PASS | PASS | PASS | PASS_WITH_AUTHORITY_BOUNDARY |
| `audit_decision_lineage` | PASS | PASS | PASS | PASS | PASS | PASS_GLOBAL_CONTRACT |
| `notifications` | PASS | PASS | PASS | PASS | PASS | PASS_WITH_AUTHORITY_BOUNDARY |
| `evidence_lineage` / `EvidenceEnvelope` | PASS | PASS | PASS | PASS | PASS | PASS_GLOBAL_CONTRACT |
| `deterministic_calculation_contract` | PASS | PASS | PASS | PASS | PASS | PASS_RECOVERY_KERNEL_SCOPE |
| `deadline_notice_window` | PASS | PASS | PARTIAL_GLOBAL / PASS_RECOVERY | PASS | PASS | PASS_RECOVERY_KERNEL_SCOPE |
| `finding_review_workflow` | PASS | PASS | PARTIAL_GLOBAL / PASS_RECOVERY | PASS | PASS | PASS_RECOVERY_KERNEL_SCOPE |
| `release_deployment_contracts` / `ReleaseEvidence` | PASS | PASS | PASS | PASS | PASS | PASS_GLOBAL_CONTRACT |
| `identity_authentication` data contract | PASS | PASS | PASS | PASS | PASS | PASS_WITH_AUTHORITY_BOUNDARY |
| `billing_interfaces` entitlement contract | PASS | PASS | PASS | PASS | PASS | PASS_WITH_AUTHORITY_BOUNDARY |
| `source_truth_verification` | PASS_NEED | PASS_LIBRARY | PASS_GITHUB_SCOPE | PASS_LIBRARY | **NOT_PROVEN_IN_REAL_WORKER_PATH** | **PARTIAL / OVERPROMOTED AS RUNTIME SHARED_VERIFIED** |
| `persistent_execution_recovery` | PASS_NEED | PASS_TESTED_SOURCE | PASS | PASS | FAIL_REAL_RUNTIME | CORRECTLY `SHARED_CONTRACT_PROPOSED` |

## Detailed findings

### 1. Tenant/role isolation — PASS with provider-authority boundary

Evidence:
- `factory_cloud/shared_platform.py::TenantContext`
- `assert_tenant_context`
- `tests/test_factory_cloud_shared_platform.py`
- Aviation + ContractCredit vertical consumers
- Industrial Claims imports and uses the same `TenantContext` and tenant assertions on its current GREEN source branch.

The contract fails closed on missing roles and cross-tenant composition. The shared boundary is tenant/actor/role context, not an identity provider.

Disposition:
`SHARED TENANT CONTEXT != SHARED PRODUCTION AUTH PROVIDER`.

Provider token verification, credentials, admin authority and production identity stores must remain independently contained unless separately approved.

### 2. Audit decision lineage — PASS at contract/source layer

`AuditEvent` records tenant, actor, type, subject, evidence references and a deterministic payload hash. Tests prove deterministic hashing and tenant isolation. Aviation, ContractCredit and current Industrial Claims source all use the shared audit primitive while retaining vertical-specific event types.

Disposition: `PASS_GLOBAL_CONTRACT`.

Audit storage/retention authority still belongs to the consuming application deployment; one cross-company production audit database is not implied.

### 3. Notifications — PASS with delivery containment

`NotificationEvent` and `InMemoryOutbox` provide tenant-bearing, idempotency-keyed notification contracts. `AssuranceStore` provides a durable notification outbox and rejects cross-tenant persistence.

The shared contract does not send provider messages itself.

Disposition:
`SHARED NOTIFICATION CONTRACT/OUTBOX != SHARED DELIVERY CREDENTIALS OR PROVIDER ACCOUNT`.

Email/SMS/push/webhook provider credentials, customer addresses and delivery authority remain consumer-owned.

### 4. Evidence lineage — PASS, now with a third source-proven consumer

`EvidenceEnvelope` remains domain-neutral. Industrial Claims current source imports and uses it in addition to Aviation + ContractCredit.

Industrial Claims adds domain-specific evidence types and a stricter intake rule: missing source content stays `REFERENCE_ONLY`; content is hashed and raw content is not persisted by the neutral envelope path. Those policies stay in the Industrial vertical.

Disposition: `PASS_GLOBAL_CONTRACT / THIRD_CONSUMER_SOURCE_PROVEN`.

### 5. Deterministic calculation contract — PASS within economic-assurance scope

`CalculationRecord` requires:
- explicit formula id and version;
- explicit inputs;
- evidence lineage;
- deterministic reproducibility hash.

Aviation uses `aviation_mr_unreimbursed_balance`.
ContractCredit uses `service_credit_percentage_of_monthly_fee`.
Industrial Claims uses its own industrial calculation semantics.

This is the correct dependency direction:

`VERTICAL FORMULA/RULE -> SHARED REPRODUCIBILITY CONTRACT`.

The shared layer must never own or silently normalize formula meaning across verticals.

Disposition: `PASS_RECOVERY_KERNEL_SCOPE`.

It is potentially broader than recovery products, but this audit does not promote it into arbitrary K3 model-calibration or ObraSignal procurement economics without a genuine compatible consumer.

### 6. Deadline window — PASS for recovery/contractual notice scope, not universal platform time semantics

`DeadlineWindow` requires supporting evidence and an explicit due date/timezone name; tests prove fail-closed missing evidence and explicit OPEN/EXPIRED behavior.

Aviation, ContractCredit and Industrial Claims all have contractual/evidence-linked deadline use cases.

However a generic platform-wide notion of deadline may require business calendars, jurisdiction rules, tolling, notice receipt rules and timezone policy that are vertical-owned.

Disposition: `PASS_RECOVERY_KERNEL_SCOPE`.

Do not interpret the shared `state_on()` helper as jurisdictional/legal deadline authority.

### 7. Finding review workflow — PASS within recovery-assurance scope; not globally domain-neutral

`FindingRecord` enforces:
- explicit evidence before supported states;
- READY_FOR_REVIEW before human review;
- reviewer and decision reason before APPROVED/REJECTED;
- cross-tenant composition rejection.

The allowed state vocabulary also includes:
- `RECOVERED`
- `CLOSED_NO_RECOVERY`

Those are recovery-domain semantics. Therefore the record is appropriate as a shared **recovery assurance kernel** primitive, but not as a universal shared workflow for ObraSignal procurement, K3 prediction truth or Product Checker regulatory decisions.

Disposition:
`PASS_RECOVERY_KERNEL_SCOPE / DO_NOT_RELABEL_AS_GLOBAL_PLATFORM_FINDING_STATE_MACHINE`.

### 8. Exact-SHA release evidence — PASS global contract

`ReleaseEvidence` validates an exact 40-character SHA and requires every explicit required check to be successful before readiness. Aviation and ContractCredit consume the same contract.

Disposition: `PASS_GLOBAL_CONTRACT`.

The concrete ObraSignal GitHub workflow remains repository-coupled. Share the invariant, not the entire workflow body by assumption.

### 9. Identity contract — PASS only as data/authorization input contract

`IdentityPrincipal` carries tenant, subject, roles, issuer and audience. Factory Cloud's own capability inventory explicitly says provider-specific token verification remains consumer-owned.

Disposition:
`PASS_WITH_AUTHORITY_BOUNDARY`.

The capability name `identity_authentication` is broader than the concrete shared source. The safe proven claim is closer to **identity principal contract**, not one shared production authentication authority.

### 10. Billing interface — PASS only as entitlement-state contract

`EntitlementSnapshot` carries tenant, plan, status, feature set and optional provider reference. Factory Cloud evidence explicitly keeps provider billing mutations outside the shared core.

Disposition:
`PASS_WITH_AUTHORITY_BOUNDARY`.

The capability name `billing_interfaces` must not be interpreted as shared merchant account, payment credentials, invoice mutation, webhook authority or cross-company billing database.

### 11. Source-truth verification — MATERIAL PARTIAL / runtime wiring gap

Factory Cloud contains a good fail-closed library contract:
- `GitHubHeadVerifier` checks live GitHub branch head against an exact expected head;
- missing source truth => BLOCKED;
- unavailable verification => UNKNOWN;
- changed head => MISMATCH / `canonical_head_changed`;
- `VerifiedDispatchAdapter` blocks before delegation on request/source/head mismatch;
- unit tests prove these cases.

However the real persistent worker path currently does not prove use of that boundary:

`app_worker.py::_runtime_adapters`
-> `AdapterRegistry({app_id: ProcessAgentAdapter(config)})`
-> `ProcessAgentAdapter.execute()`
-> local `git rev-parse HEAD == request.target_head`
-> run app agent.

`runtime_gate.py` / `runtime_provisioning.py` also check only the local workspace HEAD against the registry expected HEAD.

The recovery app agent runs pytest and does not live-verify the remote branch head.

Therefore this unsafe sequence is currently possible in source logic:

`REGISTRY STALE HEAD == LOCAL STALE WORKSPACE HEAD`
while
`LIVE CANONICAL BRANCH HAS ADVANCED`

and the process path has no mandatory proof that catches the remote divergence immediately before execution.

This is not theoretical in the current inventory: PR #760 registry pins Industrial Claims to `529debe635aa281b0c6062a2de7f6ef580e57738`, while live `apps/industrial-claims` is `449e3e846d1ad7096b7cf6790ecc119299a35023`, 131 commits ahead and GREEN at run `33270696084`.

Owner-route evidence is recorded on PR #760 comment `5464440957`.

Independent gate result:
- G1: PASS — multiple apps need exact source verification;
- G2: PASS for the verifier library/tests;
- G3: PASS within GitHub-backed source scope;
- G4: PASS for the library contract;
- G5: **FAIL / NOT PROVEN IN REAL PERSISTENT WORKER PATH**.

Disposition:
**`SHARED_VERIFIED` IS TOO STRONG FOR THE RUNTIME PATH. CLASSIFY INDEPENDENTLY AS `SHARED_VERIFIER_LIBRARY_PROVEN / RUNTIME_INTEGRATION_PARTIAL`.`**

Required repair proof:
- mandatory live remote head check in the actual worker/pre-dispatch path;
- remote unavailable => WAIT/UNKNOWN;
- remote mismatch => WAIT/BLOCKED before app agent execution;
- regression test with stale local+registry head and newer remote head proving delegate/agent call count remains zero.

### 12. Persistent execution/recovery — current Factory Cloud state is correctly conservative

Factory Cloud already classifies this capability `SHARED_CONTRACT_PROPOSED` with no verified consumers and explicitly requires real supervised execution/restart recovery on at least two app workspaces before promotion.

Independent result:
- G1 need: PASS;
- source/tests: meaningful;
- G5 real runtime consumer proof: FAIL/PENDING.

Disposition: **KEEP CURRENT LOWER STATE. DO NOT PROMOTE.**

The runtime-provisioning wait on Aviation, ContractCredit and Industrial Claims is a correct safety boundary, not a reason to fabricate G3/G5 maturity.

## Industrial Claims as third-consumer evidence

Industrial Claims current source materially strengthens several shared-contract claims:
- uses `EvidenceEnvelope`;
- uses `CalculationRecord`;
- uses `DeadlineWindow`;
- uses `FindingRecord`;
- uses `TenantContext`;
- uses shared `AuditEvent` and `NotificationEvent`;
- uses `AssuranceStore` plus additional Industrial-owned case metadata/recovery rules.

This is good evidence of reuse **because Industrial-specific semantics remain in `vertical_apps/industrial_claims`**.

It is not permission to move Industrial claim-family rules, recovery caps, customer outcomes or evidence sufficiency policies into the generic kernel.

## Product Checker and K3 boundary

No current gate result in this document assumes Product Checker or K3 are consumers of the recovery assurance kernel.

- K3: runtime proven, canonical editable source still unknown.
- Product Market Access / Legal Product Checker: Factory Cloud explicitly lists it among research/business Factories not registered as applications; canonical app source/runtime is not established.

A capability that is safe across recovery verticals is not automatically universal across all companies.

## Required owner actions from this audit

### Factory Cloud PR #760

1. Repair mandatory live remote source-head verification in the real persistent worker path.
2. Refresh Industrial Claims registry source truth only after live-head protection is wired and tested.
3. Keep `persistent_execution_recovery` at `SHARED_CONTRACT_PROPOSED` until real supervised runtime proof exists.
4. Keep provider auth/billing authority outside shared core despite broad capability names.
5. Preserve per-app storage/trust boundaries.

### OS Side Factory PR #608

1. Remain non-runtime.
2. Track repair evidence on the owner PR rather than creating a parallel verifier/runtime.
3. Re-audit promotion state after the owner head changes.
4. Continue source-truth discovery for K3 and Product Checker without inventing ownership.

## ACTIVE / NEXT / WAIT

ACTIVE: track the source-verifier runtime integration defect on Factory Cloud, audit any owner repair at exact head, and continue remaining source/promotion checks without duplicating implementation.

NEXT: reconcile Product Checker to its explicit research/business-not-application state; re-check Factory Cloud registry/head; re-check Side Factory exact-head CI; persist an exact BATON.

WAIT: live supervised app workspaces, provider auth/billing consolidation, production credentials/customer data, production database consolidation, merge and deploy remain outside this Side Factory's authority.
