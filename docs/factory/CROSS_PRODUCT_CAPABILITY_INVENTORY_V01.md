# Cross-Product Capability Inventory v0.1

Status: OBSERVATION_ONLY / NON-RUNTIME / NO-MERGE-AUTHORIZATION

## Evidence boundary

This inventory records only capabilities proven by connected repository/runtime evidence. UNKNOWN does not mean absent.

Exact ObraSignal baseline inspected: main@66d43f6fd51cf9cea08016dad335aaa04b711a24.
Shared-platform safety branch parent: same exact main baseline.

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
| Production smoke | PROVEN_PRESENT | production-smoke workflow | CI template candidate |
| Quality workflow | PROVEN_PRESENT | quality workflow | CI template candidate |
| Web preview | PROVEN_PRESENT | web-preview workflow | deployment-template candidate |
| Mobile release preflight | PROVEN_PRESENT | mobile-release-preflight workflow | product-dependent; inspect before reuse |
| Billing setup | PROVEN_PRESENT | BILLING_SETUP.md | HIGH_BLAST_RADIUS; inventory only |
| Deployment/version controls | PROVEN_PRESENT | DEPLOYMENT_VERSION.txt and workflows | shared pattern candidate |
| Domain procurement semantics | PROVEN_PRESENT | API/profile/opportunity/workflow/source logic | DOMAIN_SPECIFIC; NEVER shared merely for reuse |

## K3 current evidence boundary

K3 Fatality is PROVEN_DEPLOYED as an independent Vercel production project from prior connected runtime inspection. Auxiliary K3 projects for historical bridge/pack and probes are existing assets and remain independently owned.

Source-tree-level capability classification for K3 remains UNKNOWN because the canonical source repository is not yet identified in connected GitHub evidence. Do not infer absence and do not rebuild capabilities based on this UNKNOWN.

## Industrial Supplier Claims

Canonical source/runtime location: UNKNOWN in connected evidence. All horizontal capability cells remain UNKNOWN until source truth is located.

## Product Checker

Canonical source/runtime location: UNKNOWN in connected evidence. All horizontal capability cells remain UNKNOWN until source truth is located.

## Duplication decisions permitted now

No capability is yet SHARED_PROVEN.

Potential low-blast-radius comparison targets once a second source tree is available:
1. CI quality/smoke templates
2. testing helpers
3. generic CORS/header normalization
4. bounded diagnostic/logging patterns
5. generic utilities

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
- have a second proven implementation/consumer;
- be domain-neutral;
- contain no production secret or customer-data authority;
- be reversible without data migration;
- have executable regression evidence;
- preserve independent deployment and version pinning.

Until those conditions exist, the correct state is INVENTORY_CONTINUE, not BUILD_SHARED.

## Next evidence tasks

1. Locate K3 canonical source truth without modifying its Vercel production project.
2. Classify K3 horizontal capabilities against this matrix.
3. Locate Industrial Supplier Claims canonical source/runtime truth.
4. Locate Product Checker canonical source/runtime truth.
5. Produce DUPLICATE_CANDIDATE matrix.
6. Select the lowest-blast-radius candidate that passes G1-G4.
7. Build a branch-only pilot and require a second consumer before SHARED_PROVEN.

## Safety invariant

UNKNOWN != ABSENT.
PRESENT != REUSABLE.
DUPLICATED != SAFE_TO_CENTRALIZE.
SHARED_SOURCE != SHARED_RUNTIME.
NO AUTOMATIC MERGE OR PRODUCTION ROLLOUT.

## ACTIVE -> NEXT -> WAIT

ACTIVE: locate canonical source truth for K3 and remaining products; classify without writes to their runtimes.
NEXT: produce evidence-backed duplicate-candidate matrix and rank first low-blast-radius pilot.
WAIT: any shared-package extraction, auth/billing changes, production rollout, data movement, or merge authorization remains blocked until required gates and explicit authority exist.
