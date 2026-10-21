# Cross-Product Source Truth Status v0.1

Status: EVIDENCE_ONLY / NON_RUNTIME / UNKNOWN_PRESERVING

## Purpose

Freeze the current source/runtime classification for the products relevant to the Shared Platform Safety Foundation so later execution does not regress to stale chat assumptions.

## ObraSignal

- repository: `MarcosTaz/Obrasignal`
- canonical main observed by this lane: `66d43f6fd51cf9cea08016dad335aaa04b711a24`
- source: PROVEN
- runtime/product source authority: PROVEN within ObraSignal owner lanes

Classification: `CANONICAL_SOURCE_PROVEN`.

## Factory Cloud Shared Platform

- repository: `MarcosTaz/Obrasignal`
- PR #760
- branch: `factory-cloud/shared-platform-portfolio-architecture`
- exact observed HEAD: `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head Quality run `33265278871`: SUCCESS

Classification: `EXECUTABLE_SHARED_IMPLEMENTATION_PROVEN / DRAFT_UNMERGED`.

Independent caveat: live remote source-head revalidation is not yet proven in the actual persistent worker path; see `FACTORY_CLOUD_SHARED_CAPABILITY_GATE_AUDIT_V01.md`.

## Industrial Supplier Claims & Margin Recovery

- repository: `MarcosTaz/Obrasignal`
- branch: `apps/industrial-claims`
- PR #785
- exact observed HEAD: `449e3e846d1ad7096b7cf6790ecc119299a35023`
- exact-head Quality run `33270696084`: SUCCESS
- source includes `vertical_apps/industrial_claims/` and dedicated tests

Classification: `CANONICAL_SOURCE_PROVEN / EXACT_HEAD_GREEN / DRAFT_UNMERGED`.

The older `factory/industrial-claims-causledger-v0.23.0` lineage is historical/pointer evidence, not the best current source truth.

## Aviation / Aircraft Lease recovery

Two distinct source facts exist and must not be collapsed:

1. `MarcosTaz/money-leakage-auditor` contains the source tree `aircraft-lease-cash-assurance/`, observed at main `8309836b6c2a23e0f2215f45d8137f5476f37412`.
2. Factory Cloud/ObraSignal contains the assisted Aviation Lease Entitlement Recovery vertical source registered under its own application branch.

Classification: `SOURCE_PROVEN_ON_MULTIPLE_EXPLICIT_SURFACES`.

Do not silently treat the evidence-pack repository and the Factory Cloud application implementation as the same artifact or ownership boundary.

## ContractCredit

Factory Cloud registry/source evidence proves the application branch and assisted vertical implementation with exact-head GREEN evidence recorded by its owner lane.

Classification: `CANONICAL_APPLICATION_SOURCE_PROVEN_IN_FACTORY_CLOUD_REGISTRY`.

## K3 Fatality / Probability Intelligence

- Vercel runtime family: PROVEN
- stable project `k3-fatality`: PROVEN
- auxiliary/versioned/probe K3 deployments: PROVEN
- connected canonical editable Git repository/source tree: NOT PROVEN

Factory Cloud itself records K3 as:
- `ACTIVE_RUNTIME_SOURCE_UNRESOLVED`
- Vercel runtime verified
- canonical repository null
- repository writes blocked until source truth resolves.

Classification:
`RUNTIME_PROVEN / CANONICAL_EDITABLE_SOURCE_UNKNOWN`.

Rules:
- runtime deployment != editable source repository;
- preview/probe/versioned project != canonical editable source by default;
- UNKNOWN must not be converted to absent.

## Product Market Access / Legal Product Checker

Factory Cloud provides a stronger classification than a generic failed search.

Its application registry explicitly excludes research/business Factories from application-development orchestration until they are promoted to a real application with canonical source/runtime truth. The explicit non-registered examples include:

`Product Market Access / Legal Product Checker`.

Direct repository branch/PR/issue/commit discovery has not established a canonical application source tree or runtime for Product Checker.

Classification:

`RESEARCH_BUSINESS_FACTORY_NOT_APPLICATION_REGISTERED / CANONICAL_APPLICATION_SOURCE_RUNTIME_NOT_ESTABLISHED`.

This is not `PROVEN_ABSENT`.

It means:
- the Factory/business thesis may exist;
- it is not currently source-registered as an application in Factory Cloud;
- no repository should be assigned to it by semantic similarity;
- application-level shared-platform adoption is premature until canonical source/runtime exists.

## Source-truth precedence

When evidence changes, use this order:

1. live canonical repository/branch exact HEAD;
2. exact owning PR/source registry with verifiable branch evidence;
3. exact runtime provider evidence for runtime-only claims;
4. durable Factory baton/source pointer;
5. conversation memory.

A lower layer cannot override contradictory higher-layer source truth.

## Current unresolved source work

1. K3 canonical editable Git source.
2. Product Checker canonical application source/runtime after/if promoted from research/business Factory to application.
3. Factory Cloud registry refresh for Industrial Claims after the owner repairs mandatory live remote-head verification in the persistent worker path.

## Safety invariant

`UNKNOWN != ABSENT.`

`RUNTIME != SOURCE.`

`RESEARCH FACTORY != REGISTERED APPLICATION.`

`SOURCE POINTER != CURRENT SOURCE TREE.`

`STALE REGISTRY != LIVE CANONICAL HEAD.`
