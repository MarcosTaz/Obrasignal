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
- generic OCDS API envelope support in `ocds_adapter.py`
- `DO_DGCP` membership in existing `OCDS_PAGE_API` family
- `DO_DGCP` registry record remains `planned`

## Runtime safety

- No new runtime fork.
- No `preload.py` change in this consolidation pass.
- `DO_DGCP` is not promoted to ready/production.
- `UY_ARCE` remains the only canonical Uruguay source identity.
- The currently wired `UY_ARCE` runtime continues to advertise TENDER only. PAC code is staged until RSS cursor + PAC snapshot composition is explicitly implemented and tested atomically.

## Source gates retained

- Peru: machine access remains gated; no connector copied into runtime.
- Panama: TLS/current-contract gates remain; no connector copied into runtime.
- Costa Rica: no engineering in current phase.
- Mexico: deferred.

## Merge semantics

Do not merge the original country PRs wholesale after this consolidation. Their evidence remains valuable, but overlapping code must be reconciled against this branch to avoid duplicate registry/family changes.

## Rollback

Revert the consolidation PR. No schema migration, deployment setting or Master Queue mutation is introduced here.
