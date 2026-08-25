# Opportunity Decision Journal / Pursuit Decision v0

**Capability status:** prepared in parallel for review. This document does not claim production integration.

## Purpose

Record the explicit company decision about an opportunity without turning analytical scores, readiness, or system recommendations into an automatic commercial commitment.

Boundary: `DISCOVERED -> ANALYSED -> DECIDED`. Outcome capture (`WON`, `LOST`, realised margin, regret/learning) remains outside this module.

## Domain contract

`OpportunityDecision` is implemented as an append-only row in `opportunity_pursuit_decisions` with `decision_id`, `account_id`, `opportunity_id`, `decision_type`, `decided_at`, actor identity/type, structured reasons, optional note, blockers/unknowns, optional readiness/evidence references, observed opportunity revision/state, optional confidence, `supersedes_decision_id`, idempotency metadata, and `created_at`.

The table is deliberately distinct from the pre-existing `opportunity_decisions` table, which stores automated commercial classification/rule outputs. These concepts must not be silently conflated.

## State semantics

- `PURSUE` — company chose to pursue/bid.
- `NO_BID` — company chose not to pursue.
- `HOLD` — decision intentionally deferred.
- `NEEDS_INFO` — material information is missing.
- `UNDECIDED` — explicit neutral state.

Readiness never automatically promotes to `PURSUE`. `SYSTEM_SUGGESTED` is an actor type, not authority to replace a human decision.

## Reasons

v0 keeps a small vocabulary: `GOOD_FIT`, `MARGIN_CONCERN`, `DEADLINE_TOO_SHORT`, `QUALIFICATION_GAP`, `CAPACITY_CONSTRAINT`, `LOCATION`, `COMMERCIAL_RISK`, `INSUFFICIENT_INFORMATION`, `STRATEGIC_PRIORITY`, `OTHER`.

Freeform notes are optional and capped; this is not a CRM/comments subsystem.

## History model

Writes are append-only. A new decision stores `supersedes_decision_id` pointing at the current journal entry. Earlier rows remain intact. The current read model resolves the tip of the supersession chain. History is deterministic by `decided_at`, then `created_at`, then internal row id.

A backdated imported decision can therefore sort earlier in chronology while still being current when it was the later journal action that superseded the previous tip.

## Tenant isolation and actors

All reads/writes are scoped by authenticated `account_id`. The API derives account identity from the request context; payload `account_id` is not authority. In provider mode, the authenticated subject is used as actor id. Actor types are `HUMAN`, `SYSTEM_SUGGESTED`, and `IMPORTED`.

## API v0

Authenticated endpoints:

- `POST /api/v1/opportunities/{id}/decision`
- `GET /api/v1/opportunities/{id}/decision`
- `GET /api/v1/opportunities/{id}/decisions`

`POST` accepts `Idempotency-Key` (payload fallback supported). Same key + same normalized request returns the original decision; key reuse with a different request returns conflict.

The API verifies the opportunity exists, snapshots observed opportunity fields, and does not update the Opportunity/tender row.

## Compatibility boundaries

Readiness and Evidence references are opaque optional references. No direct storage read/write is performed against those capabilities. Watchlist, Compare, Readiness, Requirements and Change History are parallel branches at implementation time and are not assumed present on `main`.

Watchlist may later reflect `PURSUE`; this module has no hard dependency and does not mutate Watchlist.

## Contextual UI contract

`pursuit_decision_presentation.py` exposes a small `YOUR DECISION` contract with `PURSUE`, `HOLD`, `NO-BID`, `NEEDS INFO`, plus current decision/history. It is not a new dashboard or navigation surface.

## Migration and rollback

Schema creation is idempotent (`CREATE TABLE/INDEX IF NOT EXISTS`). The capability ensures its schema before access. Production WSGI wiring registers the capability route. Rollback removes route registration while retaining the append-only audit table; dropping historical decision data is not normal rollback.

## Explicit non-goals

No Outcome Graph, Contractor DNA, automatic GO/NO-GO, portfolio optimisation, bid submission, complex approvals, or workflow engine.

## Integration note

Prepared in parallel. Does not modify canonical execution order or claim production integration.
