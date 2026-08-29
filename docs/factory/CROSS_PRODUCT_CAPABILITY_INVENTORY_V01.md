# Cross-Product Capability Inventory v0.1

Status: OBSERVATION_ONLY / NON-RUNTIME / NO-MERGE-AUTHORIZATION

## Evidence boundary

This inventory records only capabilities proven by connected repository/runtime evidence. UNKNOWN does not mean absent.

Exact ObraSignal baseline inspected: main@66d43f6fd51cf9cea08016dad335aaa04b711a24.
Shared-platform safety branch parent: same exact main baseline.

## Recovery successor classification — 2026-08-28

Factory classification: **A — UNIQUE ACTIVE SPECIALIST LANE**.

Evidence supporting that classification:
- canonical repository remains `MarcosTaz/Obrasignal`;
- this Factory remains isolated on `factory/shared-platform-safety-foundation` / PR #608;
- PR search for the shared-platform / cross-product / blast-radius mission resolves #608 as the owning lane rather than a newer replacement;
- no evidence shows this work absorbed into canonical `main`;
- Factory Cloud is a separate orchestration concern and does not replace cross-product capability safety ownership.

Exact recovered branch HEAD before recovery continuation: `b76948efc4efb6951943551ded62620a6174f04c`.

Exact-head CI at that recovered HEAD:
- Python: SUCCESS;
- Mobile: FAILURE at `npx expo-doctor`;
- later Mobile wiring and bundle smoke steps: SKIPPED;
- repository-wide status therefore: **NOT_FULLY_GREEN**.

This CI state does not authorize weakening the composed gate. Documentation-only ownership remains valid while the exact-head Mobile failure is retained as evidence.

## Source truth refresh — 2026-08-29

Repository and runtime discovery was repeated before further execution.

### ObraSignal

- canonical `main` is still exactly `66d43f6fd51cf9cea08016dad335aaa04b711a24`;
- PR #608 remains OPEN / DRAFT / UNMERGED;
- the Side Factory remains documentation-only and independently owned.

### Aircraft Lease Cash Assurance

A second real product source tree is now proven in connected GitHub evidence:
- repository: `MarcosTaz/money-leakage-auditor`;
- source path: `aircraft-lease-cash-assurance/`;
- exact observed repository main: `8309836b6c2a23e0f2215f45d8137f5476f37412`;
- durable `FACTORY_BATON.md` identifies the product as Aircraft Lease Cash Assurance and records continuous product/proof execution;
- current source surface is evidence-pack / HTML / documentation oriented;
- root `.github` is absent on the observed main and the exact observed HEAD has no GitHub Actions workflow runs.

Classification: `SECOND_PRODUCT_SOURCE_PROVEN / EXACT_HEAD_CI_NOT_PROVEN`.

This source tree may be used for future horizontal comparison, but its mere existence does not satisfy duplication or second-consumer gates for the exact-head CI candidate.

### K3 Fatality

The original Vercel project `k3-fatality` remains present. New versioned deployment projects are also present:
- `k3-fatality-v0518`;
- `k3-fatality-api-v0518`;
- `k3-fatality-deploy-probe`.

Observed `k3-fatality-v0518` latest deployment is READY and targeted to production, but its versioned project identity does not by itself replace the stable `k3-fatality` front door or establish a canonical Git source tree.

Classification remains: `RUNTIME_PROVEN / CANONICAL_EDITABLE_SOURCE_UNKNOWN`.

### Other connected repositories

`MarcosTaz/ai.revenue.recovery` currently exposes only `.gitkeep` on main despite repository history/size metadata.

`MarcosTaz/contract-os` exposes only a minimal README through the proven source surface and no `.github/workflows/quality.yml`.

Neither is promoted to Industrial Supplier Claims, Product Checker, or another named Factory without direct source evidence.

## ObraSignal proven horizontal capabilities

| Capability | State | Evidence | Shared disposition |
|---|---|---|---|
| API framework | PROVEN_PRESENT | Flask API facade and blueprints | local platform primitive; inventory before extraction |
| Authentication context | PROVEN_PRESENT | development/provider modes; bearer JWT; bounded failure categories | HIGH_BLAST_RADIUS; do not extract first |
| Account identity | PROVEN_PRESENT | RequestIdentity/account_id validation | candidate only after contract inventory |
| CORS/API headers | PROVEN_PRESENT | explicit provider-mode origin validation; no-store; build/version headers | possible low-risk generic helper after domain-name removal |
| Auth failure diagnostics | PROVEN_PRESENT | bounded logging categories without token material | possible shared pattern, not yet shared package |
| Authenticated E2E | PROVEN_PRESENT | authenticated-e2e workflow in repository | testing pattern candidate |
| Auth diagnostic/live verifier | PROVEN_PRESENT | dedicated workflows | testing/verification pattern candidate |
| Production smoke | PROVEN_PRESENT | production-smoke workflow | STRUCTURE_CANDIDATE_ONLY; current file is product/runtime coupled |
| Quality workflow | PROVEN_PRESENT | quality workflow | exact-head CI pattern candidate |
| Web preview | PROVEN_PRESENT | web-preview workflow | deployment-template candidate |
| Mobile release preflight | PROVEN_PRESENT | mobile-release-preflight workflow | product-dependent; inspect before reuse |
| Billing setup | PROVEN_PRESENT | BILLING_SETUP.md | HIGH_BLAST_RADIUS; inventory only |
| Deployment/version controls | PROVEN_PRESENT | DEPLOYMENT_VERSION.txt and workflows | shared pattern candidate |
| Domain procurement semantics | PROVEN_PRESENT | API/profile/opportunity/workflow/source logic | DOMAIN_SPECIFIC; NEVER shared merely for reuse |

## K3 current evidence boundary

K3 Fatality is **PROVEN_DEPLOYED** as an independent Vercel product family.

Connected runtime evidence includes:
- stable project: `k3-fatality`;
- stable project id: `prj_URxBn8xTEMx1rx9VHIsmRUX8wuC2`;
- versioned V0.518 projects described in the refresh section above;
- multiple probe / canonical-preview / historical auxiliary Vercel projects that are existing assets and are **NOT** promoted to canonical source merely by existence.

The connected Vercel project/deployment surface still does not expose a canonical Git repository/source-tree link. The connected GitHub installation does not expose a K3 repository. Therefore:

**K3 canonical source tree: UNKNOWN.**

Do not infer absence. Do not treat deployment artifacts, preview projects, historical bridges, probes, or runtime packaging as canonical editable source.

## Industrial Supplier Claims

Canonical source/runtime location: **UNKNOWN in connected evidence**.

The connected GitHub installation exposes repositories including `MarcosTaz/Obrasignal`, `MarcosTaz/money-leakage-auditor`, `MarcosTaz/ai.revenue.recovery`, and `MarcosTaz/contract-os`, but repository-name/content evidence does not establish any of those as the exact canonical source for **Industrial Supplier Claims & Margin Recovery**.

The connected Vercel project inventory does not expose a project identified as Industrial Supplier Claims.

UNKNOWN remains UNKNOWN; do not alias a nearby revenue/leakage repository to this product without direct evidence.

## Product Checker

Canonical source/runtime location: **UNKNOWN in connected evidence**.

Repository-name/content evidence over the connected GitHub installation does not establish a canonical source for **Product Market Access / Legal Product Checker**. The connected Vercel project inventory does not expose a project identified as Product Checker.

UNKNOWN remains UNKNOWN; do not repurpose another repository based on semantic similarity.

## Low-blast-radius contract deepening

### Exact-head CI pattern — PRECLASSIFIED_CANDIDATE

The current ObraSignal Quality workflow establishes a useful low-blast-radius pattern:
1. derive the exact revision under test from PR head SHA or push SHA;
2. checkout that exact revision;
3. assert `git rev-parse HEAD` equals the expected revision before tests;
4. run product-owned test jobs independently;
5. classify the candidate only from exact-head results.

The full provider-neutral contract is now persisted in:
`docs/factory/SHARED_EXACT_HEAD_CI_CONTRACT_V01.md`.

Why this is lower blast radius than auth/billing/persistence sharing:
- no customer-data authority;
- no production secret authority;
- no database migration;
- no runtime identity ownership;
- reversible as CI configuration;
- executable evidence is intrinsic to the workflow.

Current ObraSignal-specific coupling that MUST NOT be copied blindly:
- environment/name `OBRASIGNAL_TEST_SHA`;
- Python requirements/test layout;
- `mobile` working directory;
- Expo-specific doctor and smoke commands.

Current gate state:
- G1 DUPLICATION: NOT PASSED;
- G2 STABILITY: PARTIAL;
- G3 DOMAIN NEUTRALITY: CONTRACT_PASSING;
- G4 CONTRACT: PASSING_AT_V0_1;
- G5 SECOND CONSUMER: NOT PASSED.

Disposition: **PRECLASSIFIED_CANDIDATE / NOT DUPLICATE_CANDIDATE / NOT SHARED**.

### Production smoke structure — HIGHER_COUPLING

The existing production smoke workflow contains potentially reusable structural ideas — exact deployed-build assertion, bounded retries, protected-boundary check, CORS preflight, web-shell smoke — but the concrete implementation is tightly bound to ObraSignal production URLs, service identity, provider-auth semantics, and deployment topology.

Disposition: do not extract the current workflow as the first pilot. Only compare its abstract contract after a second consumer is source-proven.

## Duplication decisions permitted now

No capability is yet SHARED_PROVEN.

A second product source tree is now proven through Aircraft Lease Cash Assurance, but no equivalent exact-head CI implementation is proven there. Therefore exact-head CI is still **NOT** a `DUPLICATE_CANDIDATE`.

Preclassified low-blast-radius comparison order as additional source trees become available:
1. exact-head CI revision assertion pattern;
2. generic quality/test workflow skeleton;
3. bounded diagnostic/logging patterns;
4. generic CORS/header normalization;
5. generic utilities;
6. production-smoke structure only after product-specific endpoints/auth semantics are separated.

Explicitly deferred until later gates:
- authentication runtime
- tenant/account authority
- permissions
- billing
- databases
- secrets
- production storage

## First-pilot selection rule

The first pilot MUST:
- have a second proven implementation/consumer, not merely a second repository;
- be domain-neutral;
- contain no production secret or customer-data authority;
- be reversible without data migration;
- have executable regression evidence;
- preserve independent deployment and version pinning.

Until those conditions exist, the correct state is INVENTORY_CONTINUE, not BUILD_SHARED.

## Next evidence tasks

1. Keep K3 canonical source discovery open without modifying its Vercel production projects.
2. Keep Industrial Supplier Claims canonical source/runtime discovery open.
3. Keep Product Checker canonical source/runtime discovery open.
4. Use Aircraft Lease Cash Assurance as a proven second source tree for low-risk capability comparison, but do not manufacture equivalence where none exists.
5. On the first source-proven equivalent horizontal implementation, produce the evidence-backed `DUPLICATE_CANDIDATE` matrix.
6. Select the lowest-blast-radius candidate that passes G1-G4.
7. Build a branch-only pilot and require a real second consumer before `SHARED_PROVEN`.

## Safety invariant

UNKNOWN != ABSENT.
PRESENT != REUSABLE.
SECOND_SOURCE != SECOND_CONSUMER.
DUPLICATED != SAFE_TO_CENTRALIZE.
SHARED_SOURCE != SHARED_RUNTIME.
NO AUTOMATIC MERGE OR PRODUCTION ROLLOUT.

## ACTIVE -> NEXT -> WAIT

ACTIVE: classify low-risk horizontal capabilities against the proven Aircraft Lease Cash Assurance source tree and continue source discovery for K3, Industrial Supplier Claims, and Product Checker; do not extract shared runtime code.
NEXT: the first source-proven equivalent horizontal implementation triggers the evidence-backed `DUPLICATE_CANDIDATE` matrix and G1-G4 evaluation.
WAIT: shared-package extraction, auth/billing changes, production rollout, data movement, merge authorization, and any second-consumer-dependent promotion remain blocked until the required gates exist.

## Autonomous safe work while source truth is blocked

Continue with non-destructive work rather than inventing equivalence:
- deepen ObraSignal capability contracts;
- compare source-proven product surfaces;
- classify domain coupling and blast radius;
- define evidence requirements for each candidate;
- keep second-consumer-dependent promotion gates closed.

Do not manufacture a second consumer merely to satisfy G1/G5.
