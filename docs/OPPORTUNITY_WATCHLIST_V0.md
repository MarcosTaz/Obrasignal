# ObraSignal Opportunity Watchlist / Saved Opportunities v0

## PURPOSE

Provide one small, tenant-private relationship between an ObraSignal account and a canonical opportunity so a contractor can mark **“this matters to my company”**, return to it later, and update its manual intent without changing the opportunity's market lifecycle.

This module is prepared in parallel. It does not modify the canonical Master Execution Queue and does not claim production integration.

## NON-GOALS

This is not a CRM, bid-management suite, task system, notification engine, Outcome Graph, Contractor DNA, COMMAND recommendation engine, Mobilize workflow, Value Created ledger, collaboration system, document store, or sales forecast.

Saving an opportunity is engagement evidence only. It is **not** evidence that value was created.

## CURRENT REPOSITORY STATE

Before this branch, `opportunity_workflow.py` already stored one account-scoped record per `(account_id, source, external_id)` with `status`, `note`, and `updated_at`. The mobile API already exposed per-opportunity workflow GET/POST operations and embedded workflow state in opportunity responses.

V0 therefore extends that existing relationship instead of introducing a competing `saved_opportunities` table.

Canonical opportunity content remains in the legacy `tenders` persistence path currently used by the product API. Watchlist stores only the canonical source identity and account-private relationship state.

## DOMAIN MODEL

The existing `opportunity_workflow` relationship now contains:

- `account_id` — tenant identity, derived server-side for API operations;
- `source` + `external_id` — canonical opportunity identity already used by the repository;
- `status` — the account's manual workflow state;
- `priority` — `LOW | NORMAL | HIGH`;
- `note` — optional private note, maximum 500 characters;
- `saved_at` — UTC timestamp; non-null means the opportunity is in the account watchlist;
- `updated_at` — UTC timestamp for the latest relationship mutation.

The database uniqueness constraint remains `(account_id, source, external_id)`. Saving the same opportunity twice therefore cannot create duplicate relationship rows.

## STATUS SEMANTICS

Existing repository terminology is preserved rather than replaced by a second state vocabulary:

- `NEW` — no active review step yet;
- `REVIEWING` — being assessed;
- `PREPARING` — preparing a response/bid;
- `SUBMITTED` — submitted;
- `DISMISSED` — explicitly not pursuing;
- `WON` / `LOST` — retained for backwards compatibility with the pre-existing workflow contract.

`WON` and `LOST` are not expanded in this module. A future Outcome Graph should become the authoritative outcome model rather than growing outcome intelligence inside Watchlist.

Watchlist membership is **not** represented by `status`; it is represented independently by `saved_at`. This avoids conflating “saved” with review/pursuit state.

## OPPORTUNITY LIFECYCLE BOUNDARY

Official/source lifecycle remains separate from company intent.

Example:

- source lifecycle: `CLOSED`, `is_actionable=false`;
- account relationship: `saved_at=<timestamp>`, `status=REVIEWING`, `priority=HIGH`.

The saved list left-joins `opportunity_lifecycle` and does not filter closed/non-actionable records. A saved opportunity therefore remains historically visible after closing or expiring.

## PERSISTENCE AND MIGRATION

`ensure_workflow_table()` performs an additive SQLite migration:

1. preserve the existing table and rows;
2. add `priority TEXT NOT NULL DEFAULT 'NORMAL'` when absent;
3. add nullable `saved_at TEXT` when absent;
4. add account/saved and account/status/priority indexes;
5. keep the pre-existing uniqueness constraint.

Existing workflow records migrate as **not saved** (`saved_at IS NULL`) and keep their previous status/note/updated timestamp.

No new database is introduced.

### Unsave semantics

`unsave` clears `saved_at` instead of deleting the workflow row. This keeps already-recorded manual status, priority and note intact while removing the item from the saved list. Re-saving later establishes a new `saved_at` timestamp.

This is deliberately lighter than event sourcing. V0 provides current state plus timestamps, not full transition history.

## SERVICE CONTRACT

`opportunity_workflow.py` exposes:

- `save_opportunity(conn, account_id, opportunity_id)` — validates canonical opportunity existence and saves idempotently;
- `unsave_opportunity(...)` — removes watchlist membership without destroying workflow state;
- `get_saved_opportunity(...)` — tenant-scoped saved relationship lookup;
- `update_saved_opportunity(..., status, priority, note)` — validated account-private mutation;
- `list_saved_opportunities(..., status, priority, order, limit, offset)` — filtered/paginated account list.

Legacy `get_workflow`, `set_workflow`, and `workflow_counts` remain compatible and now expose `priority`, `saved_at`, and `is_saved` where appropriate.

## API CONTRACT

The isolated `opportunity_watchlist_api.py` blueprint exposes:

- `POST /api/v1/opportunities/{id}/save`
- `DELETE /api/v1/opportunities/{id}/save`
- `GET /api/v1/opportunities/{id}/watch`
- `PATCH /api/v1/opportunities/{id}/watch`
- `GET /api/v1/opportunities/saved`

Supported PATCH fields are only `status`, `priority`, and `note`. Unknown fields are rejected.

Saved-list filters:

- `status`
- `priority`

Saved-list ordering:

- `recent`
- `deadline`
- `priority`

Pagination uses bounded `limit` (1–100) and non-negative `offset`.

## TENANT ISOLATION / AUTHORIZATION

The HTTP contract never accepts client-controlled `account_id` as authority. Account identity comes from the existing `configured_identity()` request context.

Every read, update, list, and unsave predicate includes that derived account id. Cross-account mutation does not fall back to a global/default row.

The existing billing guard already protects the `/api/v1/opportunities` namespace. Watchlist does not create a new billing or entitlement policy.

## INPUT VALIDATION / SECURITY

- opportunity IDs must resolve to an existing canonical opportunity before first save;
- status is allow-listed;
- priority is allow-listed;
- note is optional, stripped, parameterized, and capped at 500 characters;
- unsupported PATCH keys are rejected;
- list order is allow-listed rather than interpolated from arbitrary SQL;
- values used in SQL filters/notes are bound parameters;
- account identity is server-derived;
- no private note contents are added to logs.

## IDEMPOTENCY

A second save of an already-saved opportunity returns the existing relationship and does not update `saved_at` or `updated_at`.

This means repeated user taps/retries do not create duplicate records or manufacture artificial engagement timestamps.

## EVENTS

No new event bus or domain events are introduced in V0. The repository does not currently expose a stable generic event contract that warrants coupling this capability to one.

Future consumers may emit/consume engagement events after a canonical event/audit path exists, but `opportunity.saved` must never be interpreted as `value_created`.

## INTEGRATION POINTS

Current branch integration points are intentionally narrow:

- existing `opportunity_workflow` persistence;
- canonical `tenders` opportunity identity;
- `opportunity_lifecycle` read model for closed/archived semantics;
- existing account identity/authentication;
- existing opportunity namespace billing guard;
- production WSGI registration in `cors_app.py`;
- existing mobile opportunity-detail surface and central `mobile/src/api.js` client.

The existing opportunity list/detail already embeds `get_workflow(...)`; after this migration that object includes `is_saved`, `priority`, and `saved_at`.

## UI

V0 adds a single touch-friendly control to the existing opportunity detail surface. It does not add a new navigation area or dashboard.

Copy is deliberately explicit:

- `Guardar oportunidade`
- `Guardada`
- accessibility label `Remover das guardadas` when saved.

The control is not optimistic: local UI changes to saved/unsaved only after the backend returns success. A failed write preserves the previous state and renders an error message with alert semantics. The button exposes an accessibility role, contextual label, disabled state, and selected state.

A dedicated Saved list screen is not added in this branch; the backend endpoint `GET /api/v1/opportunities/saved` is ready for that future surface.

## TESTS

`tests/test_opportunity_watchlist.py` covers:

- save;
- duplicate prevention and idempotent timestamps;
- unsave semantics;
- get/list;
- status, priority and note updates;
- note clearing;
- invalid status and priority;
- oversized note;
- missing opportunity;
- tenant-isolated read, write and delete;
- filtering;
- deadline/priority ordering;
- pagination;
- closed opportunity retention;
- parameterized hostile note input;
- migration from the previous workflow schema;
- API account derivation rather than payload account id;
- API validation/authentication behavior.

`mobile/smoke-detail.mjs` additionally asserts that the detail surface contains the Save control, that save/unsave are wired to the API client, that the control carries an accessible contextual label/selected state, and that save failure has visible feedback.

## KNOWN LIMITATIONS

- V0 stores current relationship state, not transition history.
- `WON`/`LOST` remain in the legacy workflow vocabulary until Outcome Graph owns outcomes.
- `tenders` is still the product opportunity persistence used by current API paths even though the strategic architecture is evolving toward generic Signal; Watchlist references existing canonical `(source, external_id)` identity and does not introduce another opportunity copy.
- There is no dedicated Saved list screen yet; list/filter/order/pagination are available through the API contract.
- No analytics, alerting, DNA learning, COMMAND recommendation, or Value Created behavior is triggered.

## FUTURE

Potential future integrations, explicitly out of scope for V0:

- dedicated Saved view using the existing list endpoint;
- UI controls for priority/status filters where product evidence justifies them;
- canonical engagement event after event infrastructure is stable;
- transition history/audit ledger if product evidence justifies it;
- Outcome Graph ownership of WON/LOST/NO_BID/BID_SUBMITTED outcomes;
- aggregate privacy-governed learning for matching/ranking;
- COMMAND, Contractor DNA, Mobilize and Value Created consumers.

## ROLLBACK

Runtime rollback is straightforward: stop importing/registering `opportunity_watchlist_api`, remove the mobile Save control, and revert workflow behavior. The additive SQLite columns/indexes can safely remain unused; destructive down-migration is intentionally unnecessary.
