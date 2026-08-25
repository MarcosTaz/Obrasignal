# LATAM Next Wave — Consolidation Manifest

Status: integration candidate; no automatic merge.

## Base

- canonical base: `main`
- consolidation branch: `feature/latam-consolidation-v0`
- Master Execution Queue: untouched

## Consolidated code

- Dominican Republic: `dominican_republic_dgcp.py`, `dominican_republic_dgcp_pacc.py`
- reusable OCDS ReleasePackage lifecycle: `ocds_release_lifecycle.py`
- Uruguay PAC early signals: `uruguay_arce_pac.py`
- Uruguay atomic runtime composition: `uruguay_arce_runtime.py`
- generic OCDS API envelope support in `ocds_adapter.py`
- `DO_DGCP` membership in existing `OCDS_PAGE_API` family
- `DO_DGCP` registry record remains `planned`

## Runtime safety

- No new runtime fork.
- `DO_DGCP` is not promoted to ready/production.
- `UY_ARCE` remains the only canonical Uruguay source identity and preserves its existing durable RSS cursor.
- PAC is now composed atomically with the RSS tender fetch: both transports must succeed before one staged source observation is created.
- `stage_source_sync("UY_ARCE", ...)` receives TENDER + PROCUREMENT_PLAN while the legacy `fetch_base` projection receives TENDER only, preventing procurement plans from contaminating the legacy tender table.
- If PAC fails after RSS fetch, the new RSS cursor is not staged and therefore cannot advance silently.
- `preload.py` uses the composer; there is no second Uruguay runtime or second source cursor.

## Source gates retained

- Peru: machine access remains gated; no connector copied into runtime.
- Panama: TLS/current-contract gates remain; no connector copied into runtime.
- Costa Rica: no engineering in current phase.
- Mexico: deferred.

## Merge semantics

Do not merge the original country PRs wholesale after this consolidation. Their evidence remains valuable, but overlapping code must be reconciled against this branch to avoid duplicate registry/family/runtime changes.

## Rollback

Revert the consolidation PR. No schema migration, deployment setting or Master Queue mutation is introduced here.
