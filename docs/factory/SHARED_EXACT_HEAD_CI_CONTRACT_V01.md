# Shared Exact-Head CI Contract v0.1

Status: PROPOSED_CONTRACT / NON_RUNTIME / NOT_SHARED / NO_MERGE_AUTHORIZATION

## Purpose

Define the smallest domain-neutral CI contract that may later be reused across independent product repositories without sharing runtime authority, production data, secrets, deployment credentials, or product semantics.

This document does **not** create a shared package or second consumer. It makes the candidate contract explicit so future source-level comparison can be evidence-based rather than similarity-based.

## Candidate invariant

A CI result may classify a candidate only if the repository proves that the jobs actually executed against the exact revision being classified.

Required invariant:

`CLASSIFIED_REVISION == CHECKED_OUT_REVISION == TESTED_REVISION`

If exact revision identity cannot be proven, CI evidence is `UNKNOWN`, not GREEN.

## Minimum contract

A conforming implementation MUST:

1. Resolve one immutable candidate revision identifier before product tests run.
2. Checkout that exact revision rather than an implicit or moving branch tip.
3. Assert locally that the checked-out revision equals the expected candidate revision.
4. Fail closed before product tests if revision identity differs or is unavailable.
5. Run product-owned tests only after the identity assertion passes.
6. Preserve independent job results rather than converting one passing job into repository-wide GREEN.
7. Bind evidence to the exact revision in the resulting CI record.
8. Keep mergeability, deployment state, and CI success as separate facts.

## Event neutrality

The contract may be implemented for pull requests, pushes, or explicit/manual runs, but the event mechanism must not weaken revision identity.

Examples of acceptable revision sources:
- pull-request head SHA supplied by the CI provider;
- immutable push SHA;
- an explicitly supplied commit SHA validated as reachable in the target repository.

A branch name alone is not sufficient evidence because it can move between scheduling and execution.

## Product-owned surface

The shared candidate contract MUST NOT prescribe:
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
| Identity assertion passes; one product job fails | PARTIAL / NOT_FULLY_GREEN |
| Identity assertion passes; all required product jobs pass | EXACT_HEAD_GREEN for that repository candidate only |
| CI passes but deployment is unverified | CI_GREEN / DEPLOYMENT_UNKNOWN |
| Mergeable but required CI missing | TEST_EVIDENCE_UNKNOWN |

No condition above authorizes automatic merge or production deployment.

## Current ObraSignal evidence

ObraSignal's `.github/workflows/quality.yml` currently demonstrates the pattern by:
- deriving `OBRASIGNAL_TEST_SHA` from pull-request head SHA or `github.sha`;
- checking out that SHA explicitly;
- asserting `git rev-parse HEAD == OBRASIGNAL_TEST_SHA` before Python and Mobile tests;
- reporting Python and Mobile independently.

This is one proven implementation only. Product-specific names and commands are not part of the shared candidate contract.

## Current non-equivalence evidence

### Aircraft Lease Cash Assurance

`MarcosTaz/money-leakage-auditor` now contains a real Aircraft Lease Cash Assurance Factory source tree and durable Factory baton. Its present source surface is documentation / HTML / evidence-pack oriented and does not yet prove an equivalent exact-head CI implementation.

State for exact-head CI comparison: `SECOND_SOURCE_PRESENT / EQUIVALENT_CI_UNKNOWN`.

### K3 Fatality

K3 has a proven independent Vercel runtime and additional versioned V0.518 deployment projects. The connected evidence still does not expose a canonical editable Git source tree or a source-level exact-head CI implementation.

State for exact-head CI comparison: `RUNTIME_PRESENT / SOURCE_UNKNOWN`.

### Industrial Supplier Claims / Product Checker

Canonical editable source truth remains UNKNOWN on the connected evidence surface.

## G1-G5 mapping for this candidate

- **G1 DUPLICATION:** NOT PASSED. Only ObraSignal implementation is source-proven.
- **G2 STABILITY:** PARTIAL. ObraSignal exact-head mechanism is proven, but the current branch can still be repository-wide RED from independent Mobile dependency drift.
- **G3 DOMAIN NEUTRALITY:** CONTRACT_PASSING. Revision identity itself has no procurement semantics.
- **G4 CONTRACT:** PASSING_AT_V0_1. Inputs, failure semantics, evidence boundary, and exclusions are explicit here.
- **G5 SECOND CONSUMER:** NOT PASSED.

Result: `PRECLASSIFIED_CANDIDATE / NOT_SHARED`.

## Second-consumer proof requirements

Do not count a second product as a consumer merely because it uses GitHub Actions or runs tests.

To satisfy G1/G5, connected source evidence must prove that a second independent product:
1. identifies one immutable candidate revision;
2. checks out that exact revision;
3. asserts exact revision equality before product tests;
4. fails closed on mismatch;
5. preserves its own independent product test semantics;
6. does not depend on ObraSignal production secrets, data, databases, auth, billing, or deployment authority.

Only then may the two implementations be compared for a shared template/helper pilot.

## First pilot boundary

If G1-G4 later pass on two proven source trees, the first pilot should be configuration-only or test-helper-only.

Preferred blast-radius order:
1. provider-neutral revision assertion helper/pattern;
2. generic workflow skeleton with product-owned commands injected explicitly;
3. reusable evidence metadata convention.

Explicitly excluded from the first pilot:
- authentication;
- tenant/account authority;
- persistence/database adapters;
- secrets;
- billing;
- production deployment credentials;
- production smoke URLs;
- automatic cross-product dependency updates.

## Rollback and containment

Any future shared CI artifact must be independently versioned and pinned by each consumer. A new shared version must never auto-propagate across every product.

Required future migration sequence:

`LOCAL PROVEN -> SHARED CANDIDATE -> PINNED PILOT -> EXACT-HEAD PROOF IN CONSUMER A -> EXACT-HEAD PROOF IN CONSUMER B -> OPTIONAL ADOPTION`

Never:

`LOCAL REMOVED -> SHARED ASSUMED`.

## ACTIVE / NEXT / WAIT

ACTIVE: use this contract to classify newly reachable product source trees without building a shared runtime or package.

NEXT: the first source-proven second implementation triggers an evidence-backed equivalence matrix against this contract.

WAIT: extraction, shared package publication, auth/billing/persistence reuse, production rollout, data movement, and automatic merge remain blocked until the relevant gates pass.
