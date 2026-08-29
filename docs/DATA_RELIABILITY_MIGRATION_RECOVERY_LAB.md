# ObraSignal Data Reliability, Migration & Recovery Lab

Reanchored canonical baseline: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`.

This document is an ownership/safety map, not a second migration engine. Unmerged Watchlist, Workspace and Q090 schemas are candidates only.

## Canonical persistence ownership matrix

| Table | Owner | Tenant boundary | Creation / migration | Index / unique | Transaction boundary | Backup / restore | Rollback |
|---|---|---|---|---|---|---|---|
| `tenders` | app / legacy Opportunity compatibility projection | global source data | create + additive columns in `app.init_db()` | unique `(source,external_id)` | legacy projection can commit before canonical sidecar transaction | SQLite verified artifact | revert code; retain additive columns/data |
| `sync_runs` | app sync runtime | global | create in `app.init_db()` | PK | per sync write | included | retain history |
| `accounts` | `account_registry` + `evaluation_policy` | `account_id` | create + additive billing/evaluation columns | PK `account_id` | owner functions commit independently | included | code rollback; columns/data remain |
| `company_profiles` | `company_profile` | `account_id` | create lazily/startup | PK `account_id` | profile write commits before non-critical evaluation telemetry | included; corrupt JSON fails closed | never replace corrupt durable row with defaults/legacy |
| `opportunity_decisions` | `decision_log` | `account_id` | create + historical account-scope migration | owner schema | decision write transaction | included | retain historical decisions |
| `opportunity_events` | `notification_events` | `account_id` | create + historical account-scope migration | unique `event_key` | event owner transaction | included | retain events |
| `opportunity_workflow` | `opportunity_workflow` | `account_id` | create current schema | unique `(account_id,source,external_id)` | scoped upsert commit | included | retain relationship rows |
| `evaluation_events` | `evaluation_policy` | `account_id` | create during account/evaluation ensure | unique `(account_id,event_name,occurred_at)` | evaluation owner commits | included | retain audit/event history |
| `billing_webhook_events` | app billing dedupe | event-id scoped, account-independent | create startup | PK `event_id` | webhook dedupe write | included | retain dedupe state |
| `pipeline_latency` | `latency_metrics` | global operational telemetry | create startup | PK | owner commit | included | retain telemetry |
| `source_health` | `source_health` | source scoped | create startup | source identity | health updates independent from customer state | included | preserve last known diagnostics |
| `source_cursor` | `source_health` | source scoped | create startup | source identity | cursor must move only with represented canonical source state | included | never reset by guess |
| `signal_records` | `signal_store` | global normalized source data | runtime ensure | unique `(source,signal_type,external_id)` + required query indexes | canonical sidecar transaction | included | replay from source where contract permits |
| `source_record_metadata` | `source_metadata` | global source metadata | runtime ensure | unique `(source,external_id)` | same canonical sidecar transaction when ingestion path uses coupled writer | included | replay/converge |
| `opportunity_lifecycle` | `opportunity_lifecycle` | global source lifecycle | runtime ensure | unique `(source,external_id)` + actionable index | canonical sidecar transaction; #214 changes effective actionability read truth, not persistence ownership | included | preserve lifecycle rows; recompute effective read truth |

## Migration graph

Production WSGI startup now serializes the inherited additive migration graph through `storage_migration_lock.run_serialized_schema_init()` before serving/ingesting. Existing owner migrations remain authoritative and are not rewritten.

`app.init_db()` creates/migrates legacy/app owners -> account/profile/decision/event/workflow/source-health/latency owners. Runtime signal/source-metadata/lifecycle schemas remain owned by their runtime modules. The graph is additive but not globally atomic because inherited owner ensure functions can commit internally. Safety therefore requires: serialized first startup + fail-closed schema verification + idempotent rerun after partial completion.

## Executable rejection contract

`storage_contract.py` rejects missing required columns, required indexes, missing unique constraints, malformed persisted JSON, FK violations, unregistered root `CREATE TABLE` owners and unregistered executable `ALTER TABLE` targets.

## Transaction and cursor invariant

Cursor/checkpoint advancement may not precede the durable state it represents. Signal + source metadata + lifecycle + cursor paths must remain coupled where the ingestion contract promises one transaction. Legacy `tenders` is explicitly a compatibility projection and is not falsely claimed to be in the same all-representation transaction.

## Historical compatibility

Older unscoped decisions/events remain under the explicit historical `default` account migration rule. Older decisions without Evidence remain legitimate. Legacy Company Profile import is allowed only if no durable row exists. Existing cursors are preserved. Missing persistent fields are never interpreted as zero/false unless the domain contract explicitly says so.

## Candidate integration gates

### Watchlist #150
Accept only if rebased on current main and the additive `opportunity_workflow` migration runs behind the canonical serialized startup boundary, is registered in `storage_contract.py`, preserves existing rows/default semantics, passes old/partial/rerun/concurrent-first tests, and proves tenant A cannot read/update/delete/list tenant B state. Additive rollback may leave inert columns/indexes.

### Pursuit Workspace #172
Accept only if rebased on current main, all four new tables are registered with explicit tenant ownership and backup/restore coverage, and any declared FK guarantee is accompanied by connection-level `PRAGMA foreign_keys=ON` plus orphan/cascade/cross-tenant tests. Otherwise FK integrity must be documented as application-enforced only. No destructive rollback.

### Q090 Company State #223
Accept only after current-main reconciliation. Register `company_state_snapshots` as tenant-private; prove incompatible/partial schema failure, repeated startup, concurrent first-start compatibility with the shared migration boundary, append-only snapshot integrity, optimistic concurrency rollback, corrupt JSON fail-closed, backup/restore of history, and no payload logging. Its `BEGIN IMMEDIATE` write semantics are compatible in principle but must be exact-head combined with current owners before canonical integration.

## Sentinel rules

Reject any change that introduces destructive migration without independently reviewed data-retention ownership; unregistered persistence; private state without explicit tenant key; corrupt durable state converted to empty/default/healthy state; cursor false-success; hidden cross-table partial success where atomicity is promised; secret/private payload diagnostics; unenforced FK claims; or migration code without legacy/partial/rerun/concurrent-start coverage.
