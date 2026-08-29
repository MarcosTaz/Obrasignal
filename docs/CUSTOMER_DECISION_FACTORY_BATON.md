# Customer Decision & Outcome Intelligence Factory — BATON

Status: `ACTIVE / REPOSITORY-SAFE / NOT CANONICAL`

## Exact current truth

- Branch: `codex/customer-decision-intelligence-v1`
- Reconstructed exact HEAD before this BATON: `b3c211d76707fce363bdba4c8970bda0cae25754`
- Latest reconstructed artifact: `docs/CUSTOMER_DECISION_GOLDEN_HANDOFF.json`
- Existing handoff contract version: `customer-decision-golden-handoff.v1`
- Implementation authority: `false`
- Existing adversarial coverage includes UNKNOWN preservation, stale company-state review, economic UNKNOWN != zero, conflict preservation, lifecycle closure, missing outcome != LOST, NO_BID != NO_SUBMISSION, cross-tenant isolation, outcome correction, explicit customer decision and unavailable review telemetry.

## New cross-factory truth to absorb

Customer Journey owner candidate #821 is exact-head GREEN but not canonical. It introduces a company tenant distinct from authenticated actor subject and preserves actor subject separately from business storage authority.

Customer Decision must therefore preserve two identities whenever a shared-company model is eventually adopted:

- `business_tenant/account_id`: scopes company decision state;
- `actor_subject`: identifies the authenticated person who performed or changed a decision.

Do not collapse these identities. A later same-company user viewing company decision state must not rewrite who made the historical decision.

## ACTIVE

Extend the decision/audit semantics so shared-company collaboration cannot erase actor attribution or create cross-company decision authority.

## Required shared-company acceptance

1. User A and User B in the same company may read the same authorized company-scoped decision state.
2. A decision mutation records company account and actor subject as distinct fields.
3. User B reading User A's historical decision does not become the historical actor.
4. Revoked membership fails closed before private company decision state is returned or mutated.
5. User C in Company B cannot read or mutate Company A decision state.
6. Role/permission failure must not be represented as a customer `DECLINE` or `NO_BID` decision.
7. Membership or role changes do not silently rewrite prior customer decisions.
8. Audit attribution existence does not imply customer review/usefulness.

## NEXT

Create an adversarial shared-company handoff fixture covering actor-vs-tenant attribution, same-company handoff, revocation and cross-company negative cases without asserting canonical adoption of #821.

## WAIT

- #821 remains a noncanonical draft candidate.
- Endpoint-level role enforcement and persisted mutation audit attribution remain incomplete in the Customer Journey lane.
- No production/customer outcome or commercial evidence is inferred from repository tests.

## Exact next executable action

Add a repository-only JSON fixture with shared-company decision cases and forbidden semantic aliases. Keep every dependency on #821 marked `CANDIDATE_NOT_CANONICAL`.
