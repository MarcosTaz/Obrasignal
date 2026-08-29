# Cross-Product Capability Inventory v0.1

Status: OBSERVATION_ONLY / NON-RUNTIME / NO-MERGE-AUTHORIZATION

## Evidence boundary

This inventory records only capabilities and source ownership proven by connected repository/runtime evidence. `UNKNOWN` does not mean absent. A green implementation does not by itself authorize shared production authority.

Canonical ObraSignal baseline used by the Side Factory remains `main@66d43f6fd51cf9cea08016dad335aaa04b711a24` unless a product lane explicitly proves another base/head.

## Recovery-successor classification — refreshed 2026-08-29

Factory classification is now:

**C — PARTIALLY ABSORBED WITH UNIQUE REMAINDER.**

Why the earlier A classification changed:
- PR #608 was originally the only proven owner of the cross-product shared-platform mission;
- Factory Cloud PR #760 now contains executable shared-platform contracts, an assurance kernel, multi-consumer verification, capability inventory and source-truth verification;
- PR #608 therefore must not build a competing shared runtime;
- PR #608 still has a unique independent role: blast-radius policy, promotion-gate audit, domain anti-collapse review, source-truth inventory and adversarial verification of shared claims.

Detailed ownership reconciliation is persisted in:
`docs/factory/FACTORY_CLOUD_SHARED_PLATFORM_RECONCILIATION_V01.md`.

## Current source truth

### ObraSignal

- repository: `MarcosTaz/Obrasignal`;
- canonical main observed for this lane: `66d43f6fd51cf9cea08016dad335aaa04b711a24`;
- Side Factory: branch `factory/shared-platform-safety-foundation`, PR #608, OPEN / DRAFT / UNMERGED;
- Side Factory remains documentation-only.

### Factory Cloud shared-platform implementation

- PR #760: `[factory-cloud] shared platform + assurance kernel portfolio architecture`;
- branch: `factory-cloud/shared-platform-portfolio-architecture`;
- current observed HEAD: `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`;
- base: `factory-cloud/app-development-control-plane@3c39c0e221978526bfa685f0d090d98659a80012`;
- exact-head ObraSignal Quality run `33265278871`: SUCCESS;
- implementation includes `shared_contracts.py`, `shared_platform.py`, `shared_core.py`, `shared_core_manifest.json`, assurance-kernel/storage primitives, vertical consumers, source verification and capability inventory.

Classification: `EXECUTABLE_SHARED_IMPLEMENTATION_PROVEN / GREEN_AT_OBSERVED_HEAD / DRAFT_UNMERGED`.

### Aircraft Lease Cash Assurance

A real second product source tree is proven:
- repository: `MarcosTaz/money-leakage-auditor`;
- source path: `aircraft-lease-cash-assurance/`;
- exact observed repository main: `8309836b6c2a23e0f2215f45d8137f5476f37412`;
- durable Factory baton and evidence-pack source exist;
- no equivalent exact-head GitHub CI implementation was proven on that source tree.

Classification: `SECOND_PRODUCT_SOURCE_PROVEN / EXACT_HEAD_CI_NOT_PROVEN`.

### Industrial Supplier Claims

The previous `UNKNOWN` classification is obsolete.

Current best source truth:
- repository: `MarcosTaz/Obrasignal`;
- branch: `apps/industrial-claims`;
- PR #785: `Industrial Claims: fail-closed recovery cap and exact-head validation`;
- current observed HEAD: `449e3e846d1ad7096b7cf6790ecc119299a35023`;
- base: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`;
- source includes `vertical_apps/industrial_claims/` and dedicated Industrial Claims tests;
- exact-head ObraSignal Quality run `33270696084`: SUCCESS.

Classification: `CANONICAL_SOURCE_PROVEN / EXACT_HEAD_GREEN / DRAFT_UNMERGED`.

The branch `factory/industrial-claims-causledger-v0.23.0` remains historical/pointer evidence but is not the best current source truth.

### K3 Fatality

Connected Vercel evidence proves an independently deployed K3 product family, including stable `k3-fatality` plus versioned/probe assets. The connected GitHub installation still does not expose a canonical editable K3 repository/source tree.

Classification: `RUNTIME_PROVEN / CANONICAL_EDITABLE_SOURCE_UNKNOWN`.

Do not promote preview projects, historical bridges, deployment packaging or probes to canonical editable source.

### Product Market Access / Legal Product Checker

Repository branch, PR, issue and commit searches under Product Checker / market-access naming have not produced direct canonical ownership evidence. Connected Vercel project inventory also has not established a Product Checker runtime.

Classification: `CANONICAL_SOURCE_RUNTIME_UNKNOWN`.

Do not repurpose another repository or branch from semantic similarity.

### Other connected repositories

`MarcosTaz/ai.revenue.recovery` and `MarcosTaz/contract-os` have not been proven to own Industrial Claims or Product Checker. Nearby naming is insufficient evidence.

## ObraSignal proven horizontal capabilities

| Capability | State | Evidence | Side Factory disposition |
|---|---|---|---|
| API framework | PROVEN_PRESENT | Flask facade/blueprints | local primitive; no extraction from this lane |
| Authentication context | PROVEN_PRESENT | provider/development modes, bearer/JWT boundary | HIGH_BLAST_RADIUS; runtime authority remains product-owned |
| Account identity | PROVEN_PRESENT | request/account identity validation | contract comparison only |
| CORS/API headers | PROVEN_PRESENT | origin validation, headers/version controls | possible generic helper after second implementation proof |
| Auth failure diagnostics | PROVEN_PRESENT | bounded failure categories | pattern candidate only |
| Authenticated E2E | PROVEN_PRESENT | authenticated-E2E workflow | testing-pattern candidate |
| Production smoke | PROVEN_PRESENT | production-smoke workflow | STRUCTURE_ONLY; concrete workflow is product/runtime coupled |
| Quality workflow | PROVEN_PRESENT | exact-head quality workflow | workflow remains repository coupled |
| Web preview | PROVEN_PRESENT | web-preview workflow | deployment-template candidate only |
| Mobile release preflight | PROVEN_PRESENT | mobile preflight | product-dependent |
| Billing setup | PROVEN_PRESENT | billing setup/config evidence | HIGH_BLAST_RADIUS; provider authority not to be centralized here |
| Deployment/version controls | PROVEN_PRESENT | version files/workflows | shared pattern candidate |
| Procurement semantics | PROVEN_PRESENT | source/opportunity/workflow logic | DOMAIN_SPECIFIC |

## Factory Cloud shared-capability audit

Factory Cloud capability inventory currently records shared-platform/assurance capabilities including identity/entitlement contracts, tenant-role isolation, notifications, evidence lineage, deterministic calculation, deadline/finding contracts, source-truth verification and release evidence.

This Side Factory does not copy those implementations. It independently classifies the safety of the claimed shared boundary.

### Neutral EvidenceEnvelope — independent PASS

Factory Cloud `EvidenceEnvelope` is a neutral provenance container with:
- evidence id;
- tenant id;
- source type/reference;
- received timestamp;
- content hash;
- metadata.

Aviation and ContractCredit consume the same envelope/kernel while retaining different source types, formulas, entitlement rules and finding semantics.

Independent G1-G5 result:
- G1 reuse need: PASS;
- G2 stability: PASS_AT_`02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`;
- G3 domain neutrality: PASS;
- G4 explicit contract/failure boundary: PASS;
- G5 second consumer: PASS — Aviation + ContractCredit.

Disposition: `SHARED_PROVEN_AT_CONTRACT_SOURCE_LAYER`.

No shared production database/customer-data authority is implied.

### ReleaseEvidence exact-SHA contract — independent PASS

Factory Cloud `ReleaseEvidence` requires a 40-character revision SHA, explicit required checks and successful checks, and fails closed when required checks are missing. Aviation and ContractCredit both consume it.

Independent G1-G5 result: PASS at the current observed Factory Cloud head.

Disposition: `SHARED_VERIFIED_CONTRACT`.

This does **not** automatically make the concrete ObraSignal `.github/workflows/quality.yml` a portable shared CI package.

### Identity/authentication naming — contract only

Factory Cloud `IdentityPrincipal` carries tenant, subject, roles, issuer and audience. Its own capability inventory states provider-specific token verification remains consumer-owned.

Disposition:
`SHARED_IDENTITY_CONTRACT != SHARED_PRODUCTION_IDENTITY_AUTHORITY`.

Any future centralization of provider credentials, token-verification authority or cross-product admin authority requires a new blast-radius review.

### Billing naming — entitlement interface only

Factory Cloud `EntitlementSnapshot` carries tenant, plan, status and features. Factory Cloud evidence states billing-provider mutations remain outside shared core.

Disposition:
`SHARED_ENTITLEMENT_INTERFACE != SHARED_BILLING_PROVIDER_AUTHORITY`.

No merchant credentials, payment mutation, webhook authority or customer billing database is approved by this audit.

### AssuranceStore persistence containment — conditional PASS

`AssuranceStore` accepts an explicit database path and enforces tenant-scoped access/collision rules. Factory Cloud manifest states `consumer-owned storage only; no cross-app production database authority`.

Disposition: compatible with the Empire Blast-Radius Rule **only if deployments keep per-product storage authority isolated**. A single cross-company production database cannot inherit approval from the source abstraction.

## Exact-head CI contract

The provider-neutral CI contract is persisted in:
`docs/factory/SHARED_EXACT_HEAD_CI_CONTRACT_V01.md`.

The useful abstract pattern remains:
1. derive exact revision under test;
2. checkout exact revision;
3. assert checkout SHA equals expected SHA;
4. run product-owned checks;
5. classify only from exact-head evidence.

Concrete ObraSignal coupling includes repository-specific environment names, Python layout, mobile directory and Expo commands.

Current disposition of the concrete workflow: `REPOSITORY_COUPLED / NOT_SHARED_PACKAGE`.

Factory Cloud's `ReleaseEvidence` is a distinct reusable contract and has already been independently verified above.

## Low-risk comparison result

Previous source comparison against Aircraft Lease Cash Assurance correctly rejected false abstraction of source authority into a generic `trusted=true` flag.

The new Factory Cloud implementation confirms that the safe reusable seam is below product-owned authority policy: neutral evidence/provenance, deterministic lineage and explicit contracts can be shared while domain meaning remains vertical-owned.

See:
`docs/factory/CROSS_PRODUCT_LOW_RISK_COMPARISON_V01.md`.

## Domain anti-collapse rules

Remain product-owned:
- ObraSignal procurement publishers, tender/source/opportunity semantics;
- K3 prediction/model/calibration/backtest truth;
- Aviation lease applicability, maintenance-reserve/reimbursement logic, lessee/lessor direction and recovery attribution;
- Industrial Claims claims, reviewed recovery cap, evidence and margin/recovery semantics;
- ContractCredit SLA/remedy and service-credit meaning;
- Product Checker jurisdiction, regulatory evidence, legal-source and eligibility semantics.

A shared primitive may carry evidence, calculation, deadline or finding records. The vertical owns what those records mean.

## Promotion decisions permitted now

Independently supported:
- `EvidenceEnvelope` / neutral evidence-lineage source contract: SHARED_PROVEN_AT_CONTRACT_SOURCE_LAYER.
- exact-SHA `ReleaseEvidence`: SHARED_VERIFIED_CONTRACT.

Conditionally acceptable with authority restrictions:
- identity principal contract;
- entitlement snapshot contract;
- tenant-role context;
- notification/audit contracts;
- assurance persistence implementation with isolated app-owned storage.

Still not authorized by this lane:
- one production identity authority for all companies;
- one shared customer database;
- shared production secrets/service accounts;
- one merchant/billing authority for unrelated products;
- automatic shared-package rollout;
- cross-product production data access;
- automatic merge/deploy.

## Next evidence tasks

1. Audit remaining Factory Cloud shared claims individually rather than rebuilding them.
2. Verify tenant-role isolation, notifications, deterministic calculation, deadline/finding contracts and source-truth verification against G1-G5.
3. Keep K3 canonical editable-source discovery open.
4. Keep Product Checker canonical source/runtime discovery open.
5. Use Industrial Claims as a source-proven third vertical for compatibility/anti-collapse checks where appropriate.
6. Route implementation defects to the owning Factory Cloud or product lane; keep PR #608 non-runtime.

## Safety invariant

`UNKNOWN != ABSENT.`
`PRESENT != REUSABLE.`
`GREEN != SHARED_AUTHORITY.`
`SHARED CONTRACT != SHARED PRODUCTION TRUST.`
`SHARED SOURCE != SHARED RUNTIME.`
`SHARED RUNTIME PRIMITIVE != SHARED CUSTOMER DATA.`
`NO AUTOMATIC MERGE OR PRODUCTION ROLLOUT.`

## ACTIVE -> NEXT -> WAIT

ACTIVE: independently audit the remaining Factory Cloud shared capability inventory for G1-G5 correctness, blast radius, authority-name inflation, persistence containment and domain-semantic leakage; continue Product Checker/K3 source discovery opportunistically.

NEXT: extend the gate matrix across tenant-role isolation, notifications/audit lineage, deterministic calculation, deadline/finding workflows and source-truth verification; use Industrial Claims as an additional source-proven vertical where it provides real evidence.

WAIT: second shared-runtime implementation, auth/billing provider consolidation, production credentials, customer-data movement, database consolidation, production rollout, merge and deploy remain outside this Side Factory's authority.
