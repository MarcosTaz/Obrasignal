# Shared Exact-Head CI Contract v0.2

Status: CONTRACT_RECONCILED / NON_RUNTIME / NO_MERGE_AUTHORIZATION

## Purpose

Define the smallest domain-neutral exact-revision evidence contract that can be reused across independent products without sharing runtime authority, production data, secrets, deployment credentials or product semantics.

This document now distinguishes two layers that source truth has proven separately:

1. the **concrete ObraSignal GitHub Actions workflow**, which remains repository-coupled;
2. Factory Cloud's provider-neutral **`ReleaseEvidence` exact-SHA contract**, which is now a real multi-consumer shared contract.

## Candidate invariant

A CI/release result may classify a candidate only if the repository proves that the jobs/checks actually apply to the exact immutable revision being classified.

Required invariant:

`CLASSIFIED_REVISION == CHECKED_OUT_REVISION == TESTED_REVISION`.

If exact revision identity cannot be proven, evidence is `UNKNOWN`, not GREEN.

## Minimum contract

A conforming implementation MUST:

1. resolve one immutable candidate revision identifier before product checks run;
2. bind all classified checks to that exact revision;
3. fail closed if revision identity is missing or mismatched;
4. preserve independent required-check results rather than converting one passing check into global GREEN;
5. preserve mergeability, deployment state and CI success as separate facts;
6. retain product-owned commands and quality semantics outside the neutral revision/evidence contract.

For workflow implementations that perform a checkout, additionally:
- checkout the exact revision rather than a moving branch tip;
- assert locally that checked-out revision equals expected revision before product tests.

## Product-owned surface

A shared exact-head contract MUST NOT prescribe:
- programming language;
- package manager;
- repository layout;
- test framework;
- mobile/web/backend presence;
- deployment provider;
- production URLs;
- auth model;
- tenant model;
- database/storage technology;
- billing provider;
- secret names;
- domain-specific quality thresholds.

Those remain product-owned.

## Failure semantics

| Condition | Required classification |
|---|---|
| Expected revision missing | UNKNOWN / FAIL_CLOSED |
| Checkout cannot resolve expected revision | FAIL |
| Checked-out revision differs | FAIL |
| Exact identity passes; one required product check fails | PARTIAL / NOT_FULLY_GREEN |
| Exact identity passes; all required product checks pass | EXACT_HEAD_GREEN for that candidate only |
| CI passes but deployment is unverified | CI_GREEN / DEPLOYMENT_UNKNOWN |
| Mergeable but required CI missing | TEST_EVIDENCE_UNKNOWN |

No state authorizes automatic merge or production deployment.

## Concrete ObraSignal workflow evidence

ObraSignal `.github/workflows/quality.yml` demonstrates a concrete exact-head implementation by:
- deriving `OBRASIGNAL_TEST_SHA` from pull-request head SHA or `github.sha`;
- checking out that SHA explicitly;
- asserting `git rev-parse HEAD == OBRASIGNAL_TEST_SHA` before Python and Mobile tests;
- reporting Python and Mobile independently.

This implementation remains repository-coupled because its environment names, repository layout, mobile path and Expo commands are ObraSignal-specific.

Disposition:
`REPOSITORY_COUPLED / NOT_SHARED_PACKAGE`.

## Factory Cloud `ReleaseEvidence` — proven neutral seam

Factory Cloud PR #760 implements a narrower provider-neutral contract in `factory_cloud/shared_contracts.py`:
- revision must be an exact 40-character SHA;
- required checks are explicit;
- successful checks are explicit;
- readiness fails closed when any required check is missing.

Aviation and ContractCredit each consume the same `ReleaseEvidence` contract through their release modules.

Observed Factory Cloud exact HEAD:
`02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`.

Exact-head ObraSignal Quality run:
`33265278871` — SUCCESS.

Independent G1–G5 result for **the neutral `ReleaseEvidence` contract**:
- G1: PASS — two real vertical release consumers;
- G2: PASS_AT_OBSERVED_HEAD;
- G3: PASS — no vertical economics/domain semantics;
- G4: PASS — exact input/failure contract;
- G5: PASS — Aviation + ContractCredit.

Disposition:
**`SHARED_VERIFIED_CONTRACT`**.

This does not convert the entire ObraSignal workflow into a shared package.

## Current cross-product evidence

### Aircraft Lease Cash Assurance

Repository `MarcosTaz/money-leakage-auditor`, source path `aircraft-lease-cash-assurance/`, is a real second product source tree. No equivalent GitHub exact-head workflow implementation was proven on its observed source.

State for concrete workflow comparison:
`SECOND_SOURCE_PRESENT / EQUIVALENT_CI_WORKFLOW_NOT_PROVEN`.

### K3 Fatality

K3 has a proven live Vercel runtime. The current stable `k3-fatality` project has a newer READY production deployment, but connected evidence still does not expose a canonical editable Git source tree or source-level exact-head workflow.

State:
`RUNTIME_PROVEN / CANONICAL_EDITABLE_SOURCE_UNKNOWN`.

### Industrial Supplier Claims

The previous UNKNOWN statement is retired.

Canonical application source is proven:
- repository `MarcosTaz/Obrasignal`;
- branch `apps/industrial-claims`;
- PR #785;
- exact observed HEAD `449e3e846d1ad7096b7cf6790ecc119299a35023`;
- exact-head Quality run `33270696084`: SUCCESS.

Industrial Claims therefore proves a third real consumer of multiple Factory Cloud assurance contracts, but this alone does not make the concrete ObraSignal workflow portable because it lives in the same repository/workflow system.

### Product Market Access / Legal Product Checker

Factory Cloud explicitly classifies this as a research/business Factory that is **not registered as an application** until canonical application source/runtime truth exists.

State:
`RESEARCH_BUSINESS_FACTORY_NOT_APPLICATION_REGISTERED / CANONICAL_APP_SOURCE_RUNTIME_NOT_ESTABLISHED`.

## Updated G1–G5 distinction

### Concrete ObraSignal workflow/template

- G1 duplication for a portable workflow: NOT PROVEN across independent repositories.
- G2 stability: exact-head identity pattern is stable, but repository-wide jobs can fail for product-specific reasons.
- G3 domain neutrality: the revision identity invariant passes; the concrete commands do not.
- G4 contract: PASS at the invariant layer.
- G5 second independent repository consumer of the same portable workflow: NOT PROVEN.

Result:
`CONCRETE_WORKFLOW_NOT_SHARED`.

### Neutral `ReleaseEvidence` contract

G1–G5: PASS at the current Factory Cloud observed exact head.

Result:
`SHARED_VERIFIED_CONTRACT`.

## Source-head verification is a separate problem

An exact-SHA release record proves **what revision a result claims to classify**. It does not by itself prove that a persistent worker's pinned revision is still the live canonical branch head.

The Side Factory audit found a separate Factory Cloud gap:
- `GitHubHeadVerifier` / `VerifiedDispatchAdapter` correctly provide live remote-head verification as a library;
- the actual persistent worker path loads `ProcessAgentAdapter` directly and proves only local workspace HEAD == pinned request HEAD;
- runtime gate/provisioning checks are also local-workspace checks;
- therefore stale registry + stale matching local workspace can execute without mandatory live remote-head revalidation.

This is tracked in:
`docs/factory/FACTORY_CLOUD_SHARED_CAPABILITY_GATE_AUDIT_V01.md`
and Factory Cloud PR #760 comment `5464440957`.

Do not conflate:

`EXACT RESULT REVISION EVIDENCE`
with
`LIVE CANONICAL SOURCE HEAD VERIFICATION`.

Both are required for source-safe persistent execution.

## Rollback and containment

Any future shared CI artifact must be independently versioned and pinned by each consumer. A new version must never auto-propagate across every product.

Required future migration sequence:

`LOCAL PROVEN -> NEUTRAL CONTRACT -> PINNED PILOT -> EXACT-HEAD PROOF -> SECOND CONSUMER -> OPTIONAL ADOPTION`.

Never:

`LOCAL REMOVED -> SHARED ASSUMED`.

## ACTIVE / NEXT / WAIT

ACTIVE: reuse Factory Cloud's proven neutral `ReleaseEvidence` contract; keep concrete workflow bodies product-owned; independently track mandatory live source-head verification in persistent workers.

NEXT: after Factory Cloud repairs the real worker source-verification path, re-audit exact source identity from registry -> live remote branch -> local workspace -> executed checks -> release evidence.

WAIT: automatic workflow extraction, auth/billing/persistence authority sharing, production rollout, data movement, automatic merge and deploy remain outside this lane.
