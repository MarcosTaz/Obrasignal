# Shared Platform Safety Foundation

Status: PROPOSED / NON-RUNTIME / NO-MERGE-AUTHORIZATION

## Mission

Accelerate ObraSignal, K3 Fatality, Industrial Supplier Claims, Product Checker, and future products by reusing proven horizontal capabilities without creating a shared catastrophic failure domain.

## Core architecture principle

SHARED SOURCE -> INDEPENDENT DEPLOYMENTS -> ISOLATED TRUST BOUNDARIES.

Reuse implementation, contracts, tests, patterns, and tooling. Do not automatically share production identity, customer data, secrets, runtime authority, or failure domains.

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

A product must remain independently containable: it must be possible to disable, isolate, roll back, or recover one product without requiring shutdown of the others.

## Reuse rule

Before implementing a new horizontal capability, check whether an equivalent proven capability exists elsewhere.

Decision order:
1. REUSE
2. EXTEND
3. BUILD NEW

Never copy code silently. Never force domain-specific behavior into a shared abstraction merely to increase reuse.

## Domain isolation

The following remain product-owned and must not be centralized into the shared platform merely for convenience:

- ObraSignal: procurement intelligence, opportunities, procurement workflows, source authority, tender semantics.
- K3 Fatality: sports data semantics, probability models, calibration, backtests, prediction truth.
- Industrial Supplier Claims: claims, evidence, recovery logic, margin leakage/recovery semantics.
- Product Checker: jurisdictions, regulatory evidence, product eligibility and legal-source semantics.

## Shared capability candidates

Potential horizontal candidates, subject to inventory and gates:
- UI primitives and design tokens;
- generic utilities;
- logging and telemetry helpers;
- notification infrastructure;
- storage adapters;
- job/queue abstractions;
- AI gateway/client infrastructure;
- authentication libraries;
- organization/account primitives;
- permissions primitives;
- billing adapters;
- testing utilities;
- CI/CD templates;
- deployment checks;
- security baseline tooling.

## Promotion gates

A capability may be promoted to SHARED only if all gates pass:

### G1 - DUPLICATION
Equivalent functionality exists in at least two products or there is strong evidence of imminent reuse.

### G2 - STABILITY
The candidate implementation is proven stable at an exact known version/head.

### G3 - DOMAIN NEUTRALITY
The capability contains no hidden business-domain semantics belonging to one product.

### G4 - CONTRACT
Inputs, outputs, failure semantics, versioning policy, tenant boundaries, and tests are explicit.

### G5 - SECOND CONSUMER
A second product consumes the shared capability without product-specific hacks or semantic weakening.

If any gate fails: NOT SHARED. Keep the capability local.

## Safe migration protocol

Never use delete-first migration.

Required sequence:
1. Record current exact head/version and runtime behavior.
2. Build executable contract/regression tests around the current behavior.
3. Extract or package the candidate without deleting the current implementation.
4. Version the candidate independently.
5. Prove equivalence in the original product.
6. Introduce one secondary consumer in an isolated branch/environment.
7. Run regression, E2E, security, tenant-isolation, failure and rollback tests.
8. Compare old vs new behavior and evidence.
9. Adopt only if evidence is green and no semantic regression exists.
10. Retain rollback capability.
11. Remove local duplication only after stable adoption and explicit evidence.

OLD WORKS -> NEW PROVED -> CONTROLLED MIGRATION -> VERIFIED ADOPTION -> OPTIONAL OLD REMOVAL.

Never:
OLD REMOVED -> NEW ASSUMED.

## Supply-chain containment

A shared package update must never auto-propagate to every production product.

Required rollout:
1. new shared version;
2. static/contract tests;
3. canary consumer;
4. observation window and evidence;
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

Cross-product access is deny-by-default and must be explicit, minimal, auditable, and revocable.

## Dependency direction

Products may depend on versioned shared packages.
Shared packages must not depend on product-domain code.

Allowed:
product -> shared

Forbidden:
shared -> product-domain
shared -> production customer data of another product
product A runtime -> product B runtime without an explicit contract and necessity

## Initial implementation order

Prefer lower blast-radius extraction first:
1. UI primitives/design tokens
2. generic utilities
3. logging/telemetry helpers
4. testing helpers
5. notification adapters
6. storage abstractions
7. job/queue abstractions
8. AI infrastructure
9. authentication primitives
10. permissions/account primitives
11. billing adapters

Auth and billing are deliberately late because their blast radius is high.

## Current known evidence

- ObraSignal has substantial existing horizontal infrastructure including authenticated E2E, auth diagnostics/verifiers, production smoke, quality workflows, mobile release preflight, web preview, billing setup, and deployment/version controls.
- K3 Fatality has an independently deployed production Vercel project plus auxiliary validation/probe projects. Treat these as existing assets; do not rebuild or delete them as part of shared-platform work.
- Industrial Supplier Claims canonical runtime/repository location: UNKNOWN in current connected evidence.
- Product Checker canonical runtime/repository location: UNKNOWN in current connected evidence.

UNKNOWN != ABSENT.

## Inventory matrix

For every product and capability classify only as one of:
- PROVEN_PRESENT
- PROVEN_ABSENT
- UNKNOWN
- DUPLICATE_CANDIDATE
- DOMAIN_SPECIFIC
- SHARED_CANDIDATE
- SHARED_PROVEN
- BLOCKED

Never convert UNKNOWN to ABSENT.

Minimum capability inventory:
- auth
- organizations/accounts
- permissions
- billing
- notifications
- UI system
- analytics
- observability/logging
- storage
- jobs/queues
- AI infrastructure
- database/platform primitives
- CI/CD
- E2E
- deployment
- backups/recovery
- security baseline

## Change authority

This document does not authorize:
- merge to main;
- automatic merge;
- production deploy;
- credential rotation;
- database migration;
- deletion of existing systems;
- moving production data;
- changing billing provider state;
- cross-product data access;
- branch protection changes.

Any implementation must remain branch-first, reversible, exact-head, evidence-first, fail-closed, and independently reviewable.

## Future architecture (not current-state truth)

After shared capabilities are proven, future layers may include:

1. Company Starter Kit - generate new products with proven horizontal infrastructure preinstalled.
2. Factory Control Tower - show exact-head status, tests, blockers, revenue evidence, next action, dependencies and shared-version usage.
3. Reuse Detector - detect duplicate horizontal capabilities across products.
4. Compatibility Graph - map products to shared package versions and contract compatibility.
5. Safe Upgrade Engine - create branch, upgrade one package, run tests, compare behavior, and prepare a reviewable change.
6. Internal Component Registry - catalog approved shared packages and their evidence.

These are future options, not authorization to implement them automatically now.

## Permanent safety invariant

ACCELERATION MUST COME FROM ELIMINATING DUPLICATE WORK, NOT FROM REMOVING QUALITY GATES OR COLLAPSING TRUST BOUNDARIES.

A shared platform is successful only if it increases development velocity while preserving or improving security, product independence, rollback ability, tenant isolation, evidence quality, and domain correctness.
