# Pursuit Workspace / Bid Workspace v0

**Maturity:** parallel feature branch; not merged and not production-integrated.

## Purpose

Provide one tenant-private operational context for preparing an existing canonical Opportunity without turning ObraSignal into a CRM or project-management suite. The workspace aggregates canonical Opportunity identity and optional capability summaries while owning only pursuit-specific metadata and lightweight manual context.

## Non-goals

No CRM, sales pipeline, buyer contacts, email, RFQ, proposal generation, submission, signatures, project creation, kanban, Gantt, generic tasks, Office/HR/timesheets, automatic pursuit decision or COMMAND/ACTION behavior.

## Workspace-owned data

`pursuit_workspaces` owns `account_id`, `opportunity_id` reference, optional owner, workspace status, review state, submission state and timestamps. `pursuit_workspace_blockers`, `pursuit_workspace_notes` and `pursuit_workspace_questions` own only lightweight tenant-private manual context. Canonical Opportunity fields are never copied into workspace persistence.

Workspace status is `ACTIVE | ON_HOLD | CLOSED | ARCHIVED`. It is independent of pursuit decision. Review state is `NOT_REVIEWED | IN_REVIEW | REVIEWED | NEEDS_ATTENTION`. Submission state is explicit manual context: `NOT_STARTED | PREPARING | READY_FOR_FINAL_REVIEW | READY_TO_SUBMIT | SUBMITTED | UNKNOWN`; v0 never infers readiness from document count or another module.

## External providers

Optional sections are `decision`, `milestones`, `requirements`, `readiness`, `documents`, `changes`, `economics` and `evidence`. The workspace consumes them only through the small `SummaryProvider.summary(account_id, opportunity_id)` public contract registered in `ProviderRegistry`.

No provider is wired in v0 because the inspected base branch does not expose stable public workspace-consumer contracts for those feature domains. This is deliberate: unmerged feature branches are not assumed integrated and private tables are not queried.

## Graceful degradation and failure isolation

A missing provider renders `{status: UNAVAILABLE}`. A provider exception renders `{status: FAILED}` while the Opportunity, workspace-owned context and all other sections still render. Provider exceptions are not returned to clients. The read path performs no external network fetch.

## Tenant boundary and owner authorization

Every workspace lookup/mutation is keyed by the authenticated `account_id`; request payloads cannot choose an account. Notes, blockers and questions are reached only through the account-scoped workspace row. Cross-tenant access therefore returns not-found rather than exposing existence/content.

The current auth contract provides account identity and authenticated subject but no public account user-directory contract. Owner assignment therefore fails closed: a non-null owner can only equal the authenticated caller subject. Arbitrary user IDs are rejected. When a stable tenant user-directory contract exists, it can replace this conservative validator without changing workspace persistence.

## Notes, blockers and questions

Manual blockers are `OPEN | RESOLVED` and retained after resolution. Notes are small, private plain-text data (maximum 8,000 characters); rendering clients must continue normal text escaping. Questions are bounded manual records with optional source reference and owner. No comments, threads, chat or issue tracker is introduced.

## API

Additive endpoints:

- `POST /api/v1/opportunities/{id}/workspace` — idempotently create the account workspace.
- `GET /api/v1/opportunities/{id}/workspace` — aggregate current view.
- `PATCH /api/v1/opportunities/{id}/workspace` — update owner/workspace/review/submission metadata.
- `POST .../workspace/blockers` and `POST .../blockers/{blocker_id}/resolve`.
- `POST .../workspace/notes`.
- `POST .../workspace/questions`.

The production WSGI boundary imports the additive blueprint and allows PATCH in CORS. No external side effect is exposed.

## UI

No frontend is added in v0. The repository currently has multiple presentation surfaces and no stable workspace UI shell. Shipping a speculative parallel UI would increase coupling and conflict risk. The read model is deliberately shaped for a calm stacked mobile/desktop surface later: workspace/opportunity first, manual blockers/questions next, then independently status-bearing optional sections. No decorative completion percentage exists.

## Persistence / migration / rollback

Schema creation is additive, idempotent `CREATE TABLE IF NOT EXISTS` plus indexes, invoked lazily by the workspace boundary. No existing table is altered and no canonical Opportunity row is mutated. Rollback is therefore code removal plus optional later cleanup of the four isolated `pursuit_workspace*` tables; data deletion is not required to restore prior runtime behavior.

## Tests

`tests/test_pursuit_workspace.py` covers idempotency, no canonical copying/mutation, tenant privacy, owner fail-closed behavior, close/archive boundary, blocker retention, note/question bounds, missing providers, provider success/failure isolation and invalid states. `tests/test_pursuit_workspace_api.py` covers the account-scoped HTTP boundary, cross-tenant access, invalid owner/progress and oversized notes.

## Known limitations

- No public user-directory contract means owner assignment is self-only in authenticated mode and unavailable in development identity mode.
- Optional domain providers remain intentionally unwired until stable public contracts are present on the integration base.
- Questions are create/read-through-view only in v0; answer/close mutation is deferred rather than creating workflow creep.
- No UI is included in this parallel branch.
- No event/audit infrastructure is invoked because no stable workspace-specific public event/audit contract was found; database timestamps preserve minimum record chronology.

## Future integrations

After their public contracts are actually merged, adapters may expose Decision Journal, Milestones, Requirements, Readiness, Document Inventory, Change History, Bid Economics and Evidence Graph summaries. Those adapters must remain account-aware, bounded, network-free on workspace reads and isolated from provider failures.

## Architecture fit

The module is a modular-monolith capability with private persistence, explicit provider contract, no private-table reads of other capabilities, no second Opportunity source of truth, no automatic decision/action and failure-transparent optional sections. It does not modify `master_execution_queue.py` or promote COMMAND, ACTION or Office.
