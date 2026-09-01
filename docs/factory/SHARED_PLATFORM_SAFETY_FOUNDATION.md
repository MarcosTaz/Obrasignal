# Shared Platform Safety Foundation

Status: GOVERNANCE / NON-RUNTIME / NO-MERGE-AUTHORIZATION

## Mission

Accelerate ObraSignal, K3 Fatality, Industrial Supplier Claims, Product Checker, recovery verticals and future products by reusing proven horizontal capabilities without creating a shared catastrophic failure domain.

## Current role after Factory Cloud implementation

Source truth changed on 2026-08-29.

Factory Cloud PR #760 now owns executable shared-platform and assurance-kernel implementation. This Side Factory therefore does **not** build a second shared platform.

Recovery-successor classification:

**C — PARTIALLY ABSORBED WITH UNIQUE REMAINDER.**

Absorbed implementation ownership:
- versioned shared contracts;
- Factory Cloud tenant/role and shared-platform source;
- assurance-kernel/storage source;
- multi-vertical consumers;
- Factory Cloud capability inventory/source verification/runtime maturity.

Unique Side Factory remainder:
- Empire Blast-Radius Rule;
- independent G1–G5 promotion audit;
- source-truth inventory and UNKNOWN preservation;
- authority-boundary review;
- domain anti-collapse review;
- migration/rollback/supply-chain containment policy;
- adversarial verification that green shared code does not silently become shared production trust.

Detailed reconciliation:
`docs/factory/FACTORY_CLOUD_SHARED_PLATFORM_RECONCILIATION_V01.md`.

## Core architecture principle

`SHARED SOURCE -> INDEPENDENT DEPLOYMENTS -> ISOLATED TRUST BOUNDARIES.`

Reuse implementation, contracts, tests, patterns and tooling. Do not automatically share production identity, customer data, secrets, runtime authority or failure domains.

## Empire Blast-Radius Rule

No shared capability may turn an incident in one company into an automatic incident in all companies.

Required isolation by product unless explicitly proven safe and intentionally approved:
- production databases;
- tenant/customer data;
- secrets and encryption keys;
- service accounts and tokens;
- billing credentials and webhooks;
- storage buckets/containers;
- production environments;
- admin authority;
- audit streams;
- backups and recovery paths;
- deployment promotion authority.

A product must remain independently containable: it must be possible to disable, isolate, roll back or recover one product without requiring shutdown of the others.

## Reuse rule

Before implementing a new horizontal capability, check whether an equivalent proven capability already exists.

Decision order:
1. REUSE
2. EXTEND
3. BUILD NEW

After Factory Cloud PR #760, `REUSE` explicitly includes inspecting existing `factory_cloud/shared_*`, assurance-kernel and shared-contract implementation before creating anything new.

Never copy code silently. Never force domain-specific behavior into a shared abstraction merely to increase reuse.

## Domain isolation

The following remain product-owned and must not be centralized merely for convenience:

- ObraSignal: procurement intelligence, opportunities, procurement workflows, source authority, tender semantics.
- K3 Fatality: sports data semantics, probability models, calibration, backtests, prediction truth.
- Industrial Supplier Claims: claims, evidence meaning, reviewed recovery caps, recovery logic and margin leakage/recovery semantics.
- Aviation recovery: lease applicability, maintenance-reserve/reimbursement economics, lessee/lessor direction and realized-recovery attribution.
- ContractCredit: SLA/remedy applicability, service-credit semantics and contractual notice meaning.
- Product Checker: jurisdictions, regulatory evidence, product eligibility and legal-source semantics.

Shared primitives may carry neutral evidence, calculations, deadlines, findings, audit events or entitlement snapshots. The vertical still owns what those records mean.

## Shared capability candidates and existing shared implementation

Potential/reviewable horizontal surfaces include:
- UI primitives and design tokens;
- generic utilities;
- logging and telemetry helpers;
- notification contracts/infrastructure;
- storage implementations with product-owned data authority;
- job/queue abstractions;
- AI gateway/client infrastructure;
- identity/authentication data contracts;
- organization/account primitives;
- permissions primitives;
- entitlement/billing interfaces;
- testing utilities;
- CI/CD contracts/templates;
- deployment checks;
- security baseline tooling.

Factory Cloud PR #760 already implements multiple shared contracts. This document does not authorize a parallel implementation; it audits the safety boundary of the existing owner.

## Promotion gates

A capability may be promoted to SHARED only if all gates pass:

### G1 - DUPLICATION / REUSE NEED
Equivalent functionality is required by at least two products or there is strong evidence of imminent genuine reuse.

### G2 - STABILITY
The candidate implementation is proven stable at an exact known version/head.

### G3 - DOMAIN NEUTRALITY
The capability contains no hidden business-domain semantics belonging to one product.

### G4 - CONTRACT
Inputs, outputs, failure semantics, versioning policy, tenant boundaries and tests are explicit.

### G5 - SECOND CONSUMER
A second product consumes the shared capability without product-specific hacks or semantic weakening.

If any gate fails: NOT SHARED. Keep the capability local or at its lower promotion state.

A capability may satisfy these gates at a **contract/source layer** while still failing approval for shared production authority. Promotion labels must state which layer is proven.

## Safe migration protocol

Never use delete-first migration.

Required sequence:
1. Record current exact head/version and runtime behavior.
2. Build executable contract/regression tests around current behavior.
3. Extract/package only if an existing owner does not already provide the safe shared seam.
4. Version the candidate independently.
5. Prove equivalence in the original consumer.
6. Introduce one secondary consumer in an isolated branch/environment.
7. Run regression, E2E, security, tenant-isolation, failure and rollback tests.
8. Compare old vs new behavior and evidence.
9. Adopt only if evidence is green and no semantic regression exists.
10. Retain rollback capability.
11. Remove local duplication only after stable adoption and explicit evidence.

`OLD WORKS -> NEW PROVED -> CONTROLLED MIGRATION -> VERIFIED ADOPTION -> OPTIONAL OLD REMOVAL.`

Never:
`OLD REMOVED -> NEW ASSUMED.`

## Supply-chain containment

A shared package update must never auto-propagate to every production product.

Required rollout:
1. new shared version;
2. static/contract tests;
3. canary consumer;
4. observation/evidence;
5. second consumer;
6. staged rollout to remaining products;
7. rollback path retained.

Pin versions. No floating production dependency ranges for critical shared packages.

## Trust boundary rules

Shared code does not imply shared trust.

Each production product should, where practical, have separate:
- environment variables;
- credentials;
- databases/schemas or hard isolation boundaries;
- service identities;
- storage;
- network access policies;
- deployment projects;
- billing/webhook secrets;
- encryption material;
- admin roles;
- backups.

Cross-product access is deny-by-default and must be explicit, minimal, auditable and revocable.

## Dependency direction

Products may depend on versioned shared packages.
Shared packages must not depend on product-domain code.

Allowed:
`product -> shared`.

Forbidden:
- `shared -> product-domain`;
- `shared -> production customer data of another product`;
- `product A runtime -> product B runtime` without an explicit necessity/contract.

## Blast-radius ordering

Prefer lower-blast-radius sharing first:
1. pure contracts / release-evidence invariants;
2. generic utilities;
3. logging/telemetry helpers;
4. testing helpers;
5. neutral evidence/lineage primitives;
6. notification contracts;
7. storage abstractions with isolated product-owned storage;
8. job/queue abstractions;
9. AI infrastructure;
10. identity/authentication contracts;
11. permissions/account primitives;
12. entitlement/billing interfaces.

Actual auth-provider and billing-provider authority remain later/higher-risk than provider-neutral contracts carrying identity or entitlement state.

## Current known evidence — refreshed 2026-08-29

### ObraSignal

Substantial horizontal infrastructure exists, including authenticated E2E, auth diagnostics/verifiers, production smoke, quality workflows, mobile release preflight, web preview, billing setup and deployment/version controls.

### Factory Cloud

PR #760 / branch `factory-cloud/shared-platform-portfolio-architecture` contains executable shared-platform/assurance implementation.

Observed exact HEAD:
`02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`.

Exact-head ObraSignal Quality run `33265278871`: SUCCESS.

Independent Side Factory review has already verified at least these seams at the contract/source layer:
- neutral `EvidenceEnvelope` — G1–G5 PASS;
- exact-SHA `ReleaseEvidence` — G1–G5 PASS.

Provider-specific auth verification, provider billing mutations and cross-app production data authority are not included in those approvals.

### Industrial Supplier Claims

Canonical source is now proven in the ObraSignal repository:
- branch `apps/industrial-claims`;
- PR #785;
- observed HEAD `449e3e846d1ad7096b7cf6790ecc119299a35023`;
- exact-head ObraSignal Quality run `33270696084`: SUCCESS.

The old `UNKNOWN` classification is retired.

### K3 Fatality

Independent Vercel runtime is proven, including stable and versioned/probe assets. Canonical editable Git source remains UNKNOWN in connected source evidence.

### Product Checker

Canonical editable source/runtime remains UNKNOWN in connected evidence after branch/PR/issue/commit discovery attempts under direct Product Checker / market-access naming.

`UNKNOWN != ABSENT.`

## Inventory matrix

For every product/capability use explicit evidence states such as:
- PROVEN_PRESENT
- PROVEN_ABSENT
- UNKNOWN
- DOMAIN_SPECIFIC
- CANDIDATE_SHARED
- SHARED_CONTRACT_PROPOSED
- SHARED_VERIFIED
- SHARED_PROVEN_AT_CONTRACT_SOURCE_LAYER
- SHARED_CORE
- BLOCKED

A promotion state must never imply more authority than the evidence proves.

Minimum independent audit surface:
- auth/identity;
- organizations/accounts;
- permissions;
- billing/entitlements;
- notifications;
- UI system;
- analytics;
- observability/logging;
- storage;
- jobs/queues;
- AI infrastructure;
- database/platform primitives;
- CI/CD/release evidence;
- E2E;
- deployment;
- backups/recovery;
- security baseline;
- evidence lineage;
- calculation/finding/deadline contracts.

## Evidence-first inventory companions

Live Side Factory evidence:
- `docs/factory/CROSS_PRODUCT_CAPABILITY_INVENTORY_V01.md`
- `docs/factory/CROSS_PRODUCT_LOW_RISK_COMPARISON_V01.md`
- `docs/factory/SHARED_EXACT_HEAD_CI_CONTRACT_V01.md`
- `docs/factory/FACTORY_CLOUD_SHARED_PLATFORM_RECONCILIATION_V01.md`

These documents may classify evidence and safety. They do not authorize merge, deployment, cross-product runtime access or production data movement.

## Change authority

This document does not authorize:
- merge to main;
- automatic merge;
- production deploy;
- credential rotation;
- database migration/consolidation;
- deletion of existing systems;
- moving production data;
- changing billing provider state;
- cross-product data access;
- auth-provider consolidation;
- branch protection changes.

Implementation repair belongs to the canonical owning lane. PR #608 remains non-runtime unless ownership is explicitly changed by repository evidence and review.

## Existing Factory Cloud vs future options

Factory Cloud/Control Tower functionality is no longer merely hypothetical: an executable implementation lane exists and must be treated as source truth.

Future work outside this Side Factory may still include, only when evidence supports it:
1. starter-kit generation from proven versioned shared capabilities;
2. compatibility graphs across products/shared versions;
3. duplicate-capability detection;
4. safe branch-based upgrade preparation;
5. an internal registry of approved shared capabilities and evidence.

This Side Factory should audit such work rather than independently recreating the implementation.

## Permanent safety invariant

`ACCELERATION MUST COME FROM ELIMINATING DUPLICATE WORK, NOT FROM REMOVING QUALITY GATES OR COLLAPSING TRUST BOUNDARIES.`

A shared platform is successful only if it increases development velocity while preserving or improving security, product independence, rollback ability, tenant isolation, evidence quality and domain correctness.

`FACTORY CLOUD MAY OWN SHARED IMPLEMENTATION.`

`THIS SIDE FACTORY OWNS INDEPENDENT SAFETY EVIDENCE.`

`GREEN IMPLEMENTATION != SAFE CROSS-PRODUCT AUTHORITY.`
