# Cross-Product Low-Risk Capability Comparison v0.2

Status: OBSERVATION_ONLY / NON_RUNTIME / NO_DUPLICATE_SHARED_IMPLEMENTATION / NO_MERGE_AUTHORIZATION

## Evidence scope

This comparison now spans four distinct evidence surfaces rather than assuming the original two-source state is still current.

### ObraSignal
- repository: `MarcosTaz/Obrasignal`;
- canonical baseline for this Side Factory: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`;
- relevant evidence: `.github/workflows/quality.yml`, source registry/health and product-specific runtime checks.

### Aircraft Lease Cash Assurance
- repository: `MarcosTaz/money-leakage-auditor`;
- exact observed main: `8309836b6c2a23e0f2215f45d8137f5476f37412`;
- source path: `aircraft-lease-cash-assurance/`;
- no equivalent GitHub exact-head CI implementation proven on that source tree.

### Factory Cloud Shared Platform
- repository: `MarcosTaz/Obrasignal`;
- branch: `factory-cloud/shared-platform-portfolio-architecture`;
- PR #760;
- exact observed HEAD: `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`;
- exact-head ObraSignal Quality run `33265278871`: SUCCESS;
- relevant evidence: shared contracts, shared platform, assurance kernel/store, multi-vertical consumers and capability inventory.

### Industrial Supplier Claims
- repository: `MarcosTaz/Obrasignal`;
- branch: `apps/industrial-claims`;
- PR #785;
- exact observed HEAD: `449e3e846d1ad7096b7cf6790ecc119299a35023`;
- exact-head ObraSignal Quality run `33270696084`: SUCCESS;
- dedicated vertical source/tests are present.

This comparison does not infer semantic equivalence from similar nouns such as evidence, claim, entitlement, finding, tenant or billing.

## Decision matrix

| Candidate | Evidence | Classification | Action |
|---|---|---|---|
| Concrete ObraSignal exact-head CI workflow | One repository-coupled implementation; Aircraft source has no equivalent workflow | REPOSITORY_COUPLED / NOT_SHARED_PACKAGE | Keep concrete workflow local |
| Exact-SHA release evidence contract | Factory Cloud `ReleaseEvidence`; Aviation + ContractCredit consumers; exact-head green | SHARED_VERIFIED_CONTRACT | Reuse in Factory Cloud; no second implementation |
| Neutral evidence envelope | Factory Cloud `EvidenceEnvelope`; Aviation + ContractCredit consumers/tests | SHARED_PROVEN_AT_CONTRACT_SOURCE_LAYER | Reuse existing Factory Cloud implementation |
| Tenant/role context | Factory Cloud provider-neutral contract with two vertical consumers | SHARED_CONTRACT_PASS / AUTHORITY_BOUNDED | Continue isolation audit |
| Identity principal | Provider-neutral principal contract; provider token verification remains consumer-owned | SHARED_CONTRACT_PASS / HIGH_NAME_RISK | Never infer shared auth provider authority |
| Entitlement snapshot | Provider-neutral feature/plan contract; billing mutations remain outside core | SHARED_CONTRACT_PASS / HIGH_NAME_RISK | Never infer shared merchant/payment authority |
| Audit/notification events | Domain-neutral event contracts; storage/delivery authority separated | SHARED_CONTRACT_CANDIDATE | Verify persistence/delivery containment |
| Deterministic calculation record | Generic reproducibility contract with vertical-owned formula ids | SHARED_CONTRACT_CANDIDATE | Verify no formula/domain leakage |
| Deadline/finding records | Generic records used by two recovery verticals | SHARED_CONTRACT_CANDIDATE | Verify state machine/domain boundary |
| ObraSignal source-authority gating | Procurement-source trust boundary | DOMAIN_SPECIFIC_POLICY | Do not centralize policy |
| Aviation source-authority gating | Customer-specific recovery evidence boundary | DOMAIN_SPECIFIC_POLICY | Do not centralize policy |
| Cash attribution / baseline economics | Aviation-specific | DOMAIN_SPECIFIC | Never centralize for reuse |
| Industrial reviewed recovery cap | Industrial Claims-specific economic truth | DOMAIN_SPECIFIC | Never centralize for reuse |
| Production smoke workflow | ObraSignal URLs/auth/service topology coupled | STRUCTURE_ONLY | Not first shared pilot |

## Source authority — similarity that remains unsafe to flatten

ObraSignal source authority asks:

`MAY THIS PROCUREMENT SOURCE ENTER THE INGESTION TRUST BOUNDARY?`

Aircraft Lease Cash Assurance evidence authority asks:

`MAY THIS DOCUMENT/EVIDENCE SUPPORT A CUSTOMER-SPECIFIC RECOVERY CANDIDATE?`

Industrial Claims authority additionally protects reviewed claim/economic truth and recovery caps.

These are different trust layers. They must not collapse into:

`trusted=true`.

Classification remains:
`PATTERN_OVERLAP / DOMAIN-SPECIFIC POLICY / NO_SHARED_POLICY_EXTRACTION`.

## Neutral evidence seam — now implemented and independently verified

The earlier v0.1 document identified a possible neutral seam below product-owned trust policy. Factory Cloud now contains a concrete implementation of that seam.

`EvidenceEnvelope` records neutral provenance facts:
- immutable/reference identity;
- tenant identity;
- source type/reference;
- received timestamp;
- content hash;
- metadata.

It does **not** decide:
- whether a procurement source is legally/runtime trusted;
- whether a lease is applicable;
- whether a service incident creates a credit;
- whether an Industrial Claims finding is recoverable;
- whether a customer recovery has been realized.

Aviation and ContractCredit consume the same neutral record but provide different domain-owned source types, rules, calculations and findings.

Independent G1–G5 outcome at Factory Cloud HEAD `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`:
- G1: PASS;
- G2: PASS_AT_OBSERVED_HEAD;
- G3: PASS;
- G4: PASS;
- G5: PASS.

Disposition: **SHARED_PROVEN_AT_CONTRACT/SOURCE_LAYER**.

Action: reuse the Factory Cloud implementation. Do not create a parallel evidence-envelope package in PR #608.

## Exact-head distinction: workflow vs release contract

Two different things must not be conflated.

### Concrete Quality workflow

ObraSignal `.github/workflows/quality.yml` contains repository-specific Python/mobile/Expo layout and commands. It remains a repository implementation.

Disposition: `NOT_SHARED_PACKAGE`.

### `ReleaseEvidence`

Factory Cloud has extracted only the neutral truth contract:
- revision must be an exact 40-character SHA;
- required checks are explicit;
- successful checks are explicit;
- readiness fails closed when required checks are missing.

Aviation and ContractCredit both consume this exact contract.

Disposition: **SHARED_VERIFIED_CONTRACT**.

This is an example of safe abstraction: share the invariant, not the product-specific workflow body.

## Identity and billing — naming must not expand authority

Factory Cloud currently uses capability names `identity_authentication` and `billing_interfaces`.

The actual shared implementations are narrower:

- `IdentityPrincipal`: tenant/subject/roles/issuer/audience data contract;
- `EntitlementSnapshot`: tenant/plan/status/features data contract.

Factory Cloud's own capability evidence keeps provider-specific token verification and provider billing mutations outside the shared core.

Therefore:

`SHARED IDENTITY CONTRACT != SHARED AUTH PROVIDER`.

`SHARED ENTITLEMENT CONTRACT != SHARED PAYMENT/BILLING AUTHORITY`.

This Side Factory treats any future crossing of those boundaries as a fresh high-blast-radius change requiring explicit review.

## Persistence containment

Factory Cloud `AssuranceStore` is reusable source but is instantiated from an explicit database path. Its manifest states consumer-owned storage and no cross-app production database authority.

Safe interpretation:

`SHARED STORE IMPLEMENTATION + PER-APP STORAGE AUTHORITY`.

Unsafe interpretation:

`ONE PRODUCTION DATABASE FOR ALL COMPANIES`.

The latter is not approved by this comparison.

## Domain anti-collapse findings

Still product-owned:

### Aviation
- lessee/lessor direction;
- maintenance-reserve/reimbursement semantics;
- executed-clause applicability;
- recovery eligibility and realized-cash attribution.

### ContractCredit
- SLA breach/remedy meaning;
- service-credit formula/rule selection;
- contractual notice applicability.

### Industrial Supplier Claims
- claim/evidence meaning;
- reviewed net-potential/recovery cap;
- margin leakage/recovery semantics;
- customer outcome truth.

### ObraSignal
- procurement-source authority;
- tender/opportunity/workflow semantics.

Shared records may transport evidence/calculations/findings. Verticals continue to own their meaning.

## Current ranking

1. **Neutral EvidenceEnvelope** — already implemented by Factory Cloud and independently verified; REUSE, do not rebuild.
2. **Exact-SHA ReleaseEvidence** — already implemented and multi-consumer; REUSE, do not rebuild.
3. **Tenant/role isolation** — low runtime-data authority but security sensitive; continue G1–G5/blast-radius audit.
4. **Audit/notification contracts** — promising, but persistence/delivery containment must be verified.
5. **Deterministic calculation contract** — promising if formula/rule semantics remain vertical-owned.
6. **Deadline/finding contracts** — promising if domain state-machine meaning is not over-generalized.
7. **Concrete CI workflow / production smoke** — repository/runtime coupled; share only abstract contracts unless a true second implementation proves more.
8. **Auth/billing provider authority** — high blast radius; remain product/merchant/provider isolated.

## ACTIVE / NEXT / WAIT

ACTIVE: audit the remaining Factory Cloud shared claims instead of creating competing shared infrastructure.

NEXT: independently evaluate tenant-role isolation, audit/notification, deterministic calculation, deadline/finding and source-truth verification; include Industrial Claims as a third vertical only where its source proves genuine compatibility.

WAIT: no second shared-runtime implementation, schema/data consolidation, auth-provider consolidation, billing-provider consolidation, production credential sharing, automatic rollout, merge or deploy is authorized.
