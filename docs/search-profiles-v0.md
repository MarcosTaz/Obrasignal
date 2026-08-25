# Saved Search / Search Profiles v0

## Status

This document describes the implementation on `feature/search-profiles-v0`. It does not mark the capability canonical, merged, deployed, or production-promoted.

## Purpose

A `SearchProfile` stores reusable search intent. It does **not** implement a second search engine, continuous hunting, alerts, opportunity watchlisting, or pursuit decisions.

The runtime boundary is:

`SearchProfile -> canonical search contract -> existing opportunity result contract`

Both direct `GET /api/v1/opportunities` and saved-profile RUN use `query_opportunities(...)` from `search_profiles.py` at the production WSGI boundary.

## v0 model

Persisted fields:

- `profile_id`: opaque UUID-derived identifier; identity never depends on the name.
- `account_id`: derived server-side from the authenticated request context.
- `name`: required, trimmed, maximum 120 characters.
- `filters_json`: normalized JSON containing only supported search filters.
- `sort`: versioned enum; v0 supports only `score_desc_deadline_asc`.
- `created_at`, `updated_at`.
- `last_run_at`: updated only after a successful RUN.
- `is_default`: boolean; unique per account through a database unique index plus transactional handover.
- `status`: `ACTIVE` or `INVALID`.
- `filter_schema_version`: v0 is `1`.

Duplicate names are intentionally allowed. Names are labels, not identifiers. This avoids hidden rename rules and allows users to reuse a human-readable label while `profile_id` remains the stable identity.

Delete is a hard delete because the current product has no canonical soft-delete/archive convention for this preference object and v0 has no audit/legal requirement to retain deleted search intent.

## Supported filter contract

Search Profiles may persist only filters already supported by the current opportunity-search engine:

| Filter | v0 validation |
| --- | --- |
| `market` | `PT`, `EU`, `ALL`; defaults to `PT` |
| `country` | ISO-3 uppercase code |
| `q` | text, trimmed/lowercased, max 240 characters |
| `source` | canonical source token, max 64 characters |
| `open` | boolean |
| `minscore` | integer 0–100 |

Unsupported keys are rejected. JSON is capped at 4096 encoded bytes. Sort values are mapped from a fixed enum to fixed SQL and never interpreted as arbitrary database columns or expressions. Search values use SQL bind parameters.

### Deliberately not supported yet

The product brief example includes value and deadline-distance criteria such as `EUR 100k–500k` and `deadline > 10 days`. The current `/api/v1/opportunities` search contract does not implement those filters. Saved Search v0 therefore rejects them instead of inventing private search behavior. They can be added only when the canonical search engine supports and tests them.

The same rule applies to richer geography. v0 stores the existing canonical country/market codes, not free-form location strings or a parallel radius/region model.

## Filter schema evolution

Every profile stores `filter_schema_version`.

Before RUN, the profile is revalidated against the current schema and sort contract. If its schema version is no longer supported, its stored JSON is malformed, or a stored filter/sort is no longer valid:

1. the profile is marked `INVALID`;
2. RUN fails with `search_profile_needs_update`;
3. no unsupported criterion is silently dropped;
4. repairing an `INVALID` profile requires an UPDATE that explicitly supplies both a current `filters` object and a supported `sort`;
5. a rename/default-only update cannot implicitly replace unreadable or obsolete criteria with defaults;
6. a successful explicit repair moves the profile back to `ACTIVE` at the current schema version.

## Migration / startup contract

`ensure_search_profile_table(conn)` is an explicit migration/bootstrap helper. The production WSGI startup (`cors_app.py`) invokes it before serving requests.

Normal SearchProfile CREATE/READ/UPDATE/DELETE/RUN paths do **not** execute schema DDL. Focused tests trace SQL during CRUD and fail if `CREATE`, `ALTER`, or `DROP` is executed in those paths.

The migration is additive and idempotent: it creates the table plus account lookup and one-default-per-account indexes without destructive data changes.

## API

Authenticated endpoints:

- `GET /api/v1/search-profiles`
- `POST /api/v1/search-profiles`
- `GET /api/v1/search-profiles/{profile_id}`
- `PATCH /api/v1/search-profiles/{profile_id}`
- `DELETE /api/v1/search-profiles/{profile_id}`
- `POST /api/v1/search-profiles/{profile_id}/run?limit=N`

Create payload fields: `name`, `filters`, `sort`, `is_default`.

Update payload fields: `name`, `filters`, `sort`, `is_default`.

Unknown top-level fields are rejected. In particular, `account_id` is never accepted as client authority. RUN accepts no JSON fields; unexpected fields are rejected instead of ignored.

RUN returns the existing opportunity-search result shape (`items`, `count`, `market`, `generated_at`, `account_id`) rather than introducing a competing result model.

## Tenant and authorization contract

Every persistence read/write includes both `profile_id` and authenticated `account_id`. A profile from another account is indistinguishable from a nonexistent profile at the API boundary and returns 404.

The client cannot choose ownership through request JSON. The account is derived from the existing verified request identity.

## Default-profile consistency

At most one profile per account may be default. Setting a new default clears the old default and writes the new state in one SQLite transaction. A unique partial index is the database-level backstop against races or programming errors.

## Mobile integration

`mobile/src/api.js` exposes read/create/update/delete/run methods and normalizes RUN results through the same opportunity normalization used by direct search.

No new screen or navigation surface is introduced in v0. The current Radar has a compact search/filter surface but no stable CRUD interaction pattern for reusable presets; adding a rushed editor would violate the ADR's contextual-UX rule. The API/client contract is ready for a later UX slice without changing the domain model.

## Explicit boundaries

Not implemented by this module:

- scheduled or continuous execution;
- Auto-Hunt / Continuous Opportunity Hunting;
- notifications or alert policies;
- watchlisting concrete opportunities;
- GO/NO-GO or pursuit decisions;
- currency conversion;
- new ranking/matching logic;
- new geography semantics;
- automatic migration that silently discards obsolete filters.

A future alert policy may reference a SearchProfile, but saving a SearchProfile has no automatic side effect today.

## Test obligations

The branch includes focused tests for:

- strict filter/name/sort validation;
- duplicate-name identity behavior;
- unique default per account;
- tenant isolation;
- old/corrupt profile fail-closed behavior;
- explicit repair of invalid profiles without silent criterion loss;
- no schema DDL during normal CRUD paths;
- hard delete;
- direct-search versus saved-profile semantic equivalence;
- rejection of client-supplied ownership and unsupported criteria.

The repository's pull-request CI remains the authoritative execution gate: Python compile + full pytest suite and Expo/mobile checks. A test is only reported as TESTED after that workflow actually completes successfully.

## Rollback

Because the capability is additive and remains unmerged, rollback before integration is simply closing the PR/deleting the feature branch. After a future merge, runtime rollback can remove the API installation while leaving the additive `search_profiles` table inert; dropping persisted user profiles should require an explicit data-retention decision rather than being coupled to code rollback.

## Master Queue protection

This capability does not alter `master_execution_queue.py`, `CURRENT_ITEM_ID`, queue ordering, canonical capability maturity, or the gated Continuous Opportunity Hunting item. No merge is performed by this branch.
