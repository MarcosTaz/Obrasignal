# Factory Cloud / Shared Platform Reconciliation v0.1

Status: EVIDENCE_RECONCILED / NON_RUNTIME / NO_MERGE_AUTHORIZATION

## Recovery-successor classification

The OS Side Factory is now classified:

**C — PARTIALLY ABSORBED WITH UNIQUE REMAINDER.**

The previous A classification was correct when PR #608 was the only proven lane owning the shared-platform mission. That source truth changed on 2026-08-29.

Factory Cloud PR #760 now owns executable shared-platform implementation, while PR #608 retains a unique independent safety/governance role.

## Canonical evidence

### OS Side Factory / governance lane

- repository: `MarcosTaz/Obrasignal`
- branch: `factory/shared-platform-safety-foundation`
- PR: #608 — OPEN / DRAFT / UNMERGED
- recovered pre-reconciliation HEAD: `20845adc930df0b9d851150757db32203cfbecce`
- runtime mutation in this lane: none
- unique role: cross-product safety policy, blast-radius review, promotion-gate audit, source-truth inventory, adversarial verification of shared-capability claims

### Factory Cloud / implementation lane

- PR: #760 — `[factory-cloud] shared platform + assurance kernel portfolio architecture`
- branch: `factory-cloud/shared-platform-portfolio-architecture`
- current observed HEAD: `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- base: `factory-cloud/app-development-control-plane@3c39c0e221978526bfa685f0d090d98659a80012`
- exact-head ObraSignal Quality run: `33265278871`
- conclusion: SUCCESS
- implementation includes versioned shared contracts, tenant/role boundary, assurance kernel, capability inventory, source-truth verification, vertical consumers and exact-head release evidence

PR #760 is still OPEN / DRAFT / UNMERGED. Its green state is evidence, not merge or production authority.

### Industrial Supplier Claims

Source truth is now proven in the canonical repository:

- branch: `apps/industrial-claims`
- PR: #785 — `Industrial Claims: fail-closed recovery cap and exact-head validation`
- current observed HEAD: `449e3e846d1ad7096b7cf6790ecc119299a35023`
- base: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`
- exact-head ObraSignal Quality run: `33270696084`
- conclusion: SUCCESS
- source surface includes `vertical_apps/industrial_claims/` plus dedicated Industrial Claims tests

Classification: `CANONICAL_SOURCE_PROVEN / EXACT_HEAD_GREEN / DRAFT_UNMERGED`.

The older `factory/industrial-claims-causledger-v0.23.0` evidence remains useful as historical/pointer evidence but is no longer the best current source truth.

## Ownership split

### Absorbed into Factory Cloud implementation ownership

PR #608 must not duplicate or fork these implementations:

- versioned shared identity/entitlement data contracts;
- tenant/role context contract;
- shared audit-event and notification contracts;
- Evidence & Economic Assurance Kernel primitives;
- durable assurance store implementation;
- recovery vertical consumer adapters;
- Factory Cloud capability inventory and runtime maturity model;
- Factory Cloud source-truth verification implementation;
- Factory Cloud release-evidence contract.

### Unique remainder retained by this Side Factory

PR #608 remains the independent owner for:

1. Empire Blast-Radius Rule and product containment policy.
2. Independent review of whether a claimed shared capability actually satisfies G1–G5.
3. Separation of shared contract/source from shared production authority.
4. Cross-product source-truth inventory, including UNKNOWN preservation.
5. Domain-semantics anti-collapse review.
6. Migration/rollback/supply-chain containment policy.
7. Detection of capability-name inflation, where a narrow shared contract is mislabeled as broad shared runtime authority.
8. Evidence-backed reconciliation when another lane begins implementing shared infrastructure.

This lane therefore becomes a **governance/audit safety rail**, not a second shared-runtime implementation.

## Independent gate audit of Factory Cloud shared claims

### Neutral evidence envelope

Factory Cloud `EvidenceEnvelope` records:
- evidence id;
- tenant id;
- source type/reference;
- received timestamp;
- content hash;
- metadata.

It does not encode Aviation or ContractCredit business meaning. Aviation and ContractCredit each supply their own source types, formula ids, entitlement rules and finding semantics while consuming the same envelope/kernel.

Evidence:
- `factory_cloud/assurance_kernel.py`
- `factory_cloud/vertical_consumers.py`
- `tests/test_factory_cloud_vertical_consumers.py`
- exact PR #760 Quality SUCCESS at `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`

Gate result:
- G1 DUPLICATION/REUSE NEED: PASS — two distinct vertical consumers require the same neutral evidence/provenance primitive.
- G2 STABILITY: PASS_AT_OBSERVED_HEAD — exact-head CI green.
- G3 DOMAIN NEUTRALITY: PASS — business semantics remain in vertical consumers.
- G4 CONTRACT: PASS — explicit immutable/fail-closed creation and tenant-bearing schema.
- G5 SECOND CONSUMER: PASS — Aviation and ContractCredit both exercise it in source and tests.

Independent disposition: **SHARED_PROVEN_AT_CONTRACT/SOURCE_LAYER**.

This does not authorize shared production customer storage. Storage authority remains deployment/consumer owned.

### Exact-SHA release evidence contract

Factory Cloud `ReleaseEvidence` requires:
- a 40-character exact revision SHA;
- explicit required checks;
- explicit successful checks;
- fail-closed readiness if any required check is missing.

Aviation and ContractCredit both consume the same contract through their release modules.

Gate result:
- G1: PASS — two vertical release consumers.
- G2: PASS_AT_OBSERVED_HEAD — exact-head Factory Cloud CI green.
- G3: PASS — no vertical economics/domain rules in the contract.
- G4: PASS — exact inputs/failure semantics are explicit.
- G5: PASS — both Aviation and ContractCredit consume it.

Independent disposition: **SHARED_VERIFIED / CANDIDATE_FOR_SHARED_CORE OWNERSHIP IN FACTORY CLOUD**.

This is distinct from the concrete ObraSignal `.github/workflows/quality.yml` template. The workflow itself remains product/repository-coupled and is not automatically a portable shared CI package.

## High-blast-radius naming audit

Factory Cloud currently labels these capabilities `SHARED_CORE`:
- `identity_authentication`
- `billing_interfaces`

The implementation evidence shows the shared surface is intentionally narrower than those names can imply:

### Identity

`IdentityPrincipal` is a provider-neutral identity/role data contract. Provider-specific token verification remains consumer-owned according to the Factory Cloud capability inventory.

Therefore:

`SHARED IDENTITY CONTRACT != SHARED PRODUCTION IDENTITY AUTHORITY`.

### Billing

`EntitlementSnapshot` is a provider-neutral plan/status/features contract. Provider billing mutations remain outside the shared core according to Factory Cloud evidence.

Therefore:

`SHARED ENTITLEMENT INTERFACE != SHARED BILLING PROVIDER AUTHORITY`.

Independent disposition: acceptable only while those authority boundaries remain explicit, tested and non-centralized. Any future move of provider credentials, webhook authority, merchant mutation or customer billing data into one shared failure domain requires a new blast-radius review and cannot inherit approval from this contract-level audit.

## Persistence containment audit

`AssuranceStore` accepts an explicit filesystem/database path and enforces tenant-scoped reads/collisions. The Factory Cloud manifest states `consumer-owned storage only; no cross-app production database authority`.

Independent disposition: the reusable persistence implementation is compatible with the Side Factory principle only when each production application receives an independently contained storage path/authority. A single cross-company production database must not be inferred from this code.

## Domain anti-collapse findings

Still domain-owned and excluded from generic shared authority:

- Aviation maintenance-reserve economics, lease applicability and lessee/lessor direction;
- ContractCredit SLA/remedy economics and service-credit meaning;
- Industrial Claims claim/recovery/margin semantics;
- ObraSignal procurement-source and opportunity semantics;
- Product Checker jurisdiction/regulatory/product-eligibility semantics;
- K3 prediction/model/calibration semantics.

Shared primitives may carry evidence, calculations, deadlines or findings; the vertical owns what those facts mean.

## Remaining source-truth gaps

### K3 Fatality

Runtime is proven through Vercel, including the stable `k3-fatality` project and versioned/probe assets, but connected GitHub evidence still does not establish the canonical editable K3 source tree.

Classification: `RUNTIME_PROVEN / CANONICAL_EDITABLE_SOURCE_UNKNOWN`.

### Product Market Access / Legal Product Checker

Branch, commit, issue and PR searches over the connected ObraSignal source surface have not produced direct ownership evidence under Product Checker / market-access naming.

Classification remains: `CANONICAL_SOURCE_RUNTIME_UNKNOWN`.

UNKNOWN does not mean absent.

## Operating rule after reconciliation

The Side Factory must now prefer:

`AUDIT EXISTING FACTORY CLOUD SHARED IMPLEMENTATION -> FIND UNSAFE OVERREACH OR MISSING GATES -> PERSIST EVIDENCE -> ROUTE IMPLEMENTATION REPAIR TO OWNING LANE`

not:

`BUILD A SECOND SHARED PLATFORM`.

If Factory Cloud safely implements a capability and passes independent G1–G5 review, this lane records that evidence instead of recreating it.

If a shared capability violates blast-radius, domain neutrality, tenant isolation, storage separation, rollback or authority boundaries, the violation becomes ACTIVE even if Factory Cloud CI is green.

## ACTIVE / NEXT / WAIT

ACTIVE: independently audit the current Factory Cloud shared capability inventory for promotion correctness, authority-name inflation, persistence containment and domain-semantic leakage; continue Product Checker and K3 source discovery opportunistically.

NEXT: extend the independent gate matrix across remaining Factory Cloud capabilities, beginning with tenant-role isolation, notifications, deterministic calculation, deadline/finding contracts and source-truth verification; classify each as PASS / PARTIAL / FAIL without duplicating runtime code.

WAIT: no merge, production deploy, shared production credentials, customer-data movement, database consolidation, billing-provider mutation, auth-provider authority consolidation, or second shared-runtime implementation is authorized by this lane.

## Permanent invariant

`FACTORY CLOUD MAY OWN SHARED IMPLEMENTATION.`

`THIS SIDE FACTORY OWNS INDEPENDENT SAFETY EVIDENCE.`

`GREEN IMPLEMENTATION != SAFE CROSS-PRODUCT AUTHORITY.`
