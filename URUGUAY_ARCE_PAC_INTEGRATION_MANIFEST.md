# Uruguay ARCE PAC — Integration Manifest

CELL: LATAM_NEXT_WAVE
COUNTRY: UY / URY
BRANCH: `research/uy-arce-pac-v0`
PR: #196
SOURCE_IDENTITY: `UY_ARCE`
MASTER_QUEUE: MUST REMAIN UNCHANGED
AUTO_MERGE: FORBIDDEN

## Purpose

Integrate the tested PAC `PROCUREMENT_PLAN` capability into the existing Uruguay source without creating a second source identity, a second regional runtime, or a second cursor namespace for the same publisher.

## New branch-scoped implementation

- `uruguay_arce_pac.py`
- `test_uruguay_arce_pac.py`
- `test_uruguay_arce_pac_limits.py`
- `test_uruguay_arce_pac_live.py`
- `.github/workflows/uy_pac_live.yml`
- `URUGUAY_ARCE_PAC_EVIDENCE.md`

## Existing canonical components to preserve

- `uruguay_arce.py` remains the OCDS RSS/record/release TENDER connector.
- `preload.py` currently stages `UY_ARCE` TENDER rows and the OCDS cursor through `_fetch_arce_staged()`.
- `source_registry.py` already contains one `UY_ARCE` source identity in `ready` state.
- existing `UY_ARCE` source-health/cursor history must not be reset or renamed.

## Required semantic integration

### 1. Source registry

Enrich the existing `UY_ARCE` record; do not create `UY_ARCE_PAC`.

After production-path review, expected semantic enrichment is:
- add `plans` / early-signal capability;
- add `PROCUREMENT_PLAN` alongside existing `TENDER`;
- retain legal/machine gates only if PAC-specific applicability is confirmed;
- describe the source as a composite official ARCE transport only if registry conventions require it.

Do not replace the whole registry file from this branch. Parallel cells may have added sources since the branch base.

### 2. Runtime composition

PAC is a snapshot; OCDS RSS is cursor-driven. They must remain separate fetch semantics.

Safe composition invariant:
1. read current `UY_ARCE` OCDS cursor;
2. fetch TENDER incremental records without committing cursor;
3. fetch PAC snapshot independently;
4. only after **both** required components succeed, stage the combined source result with the TENDER cursor;
5. if PAC fails, do not advance the TENDER cursor as a side effect of a partially successful combined source sync;
6. if product policy later makes PAC optional/degradable, represent that explicitly in source-health contracts rather than silently swallowing the failure.

The PAC snapshot itself must never overwrite, reinterpret or advance the OCDS RSS cursor.

### 3. Idempotency / identity

- TENDER identities stay unchanged.
- PAC identity is `pac:{procedure_id}` under source `UY_ARCE` and signal type `PROCUREMENT_PLAN`.
- preserve signal type when deduping/persisting if the global storage key is not already type-aware.
- never map PAC procedure IDs into OCDS OCIDs.

### 4. Construction admission

Keep:
- server-side `codFamilia=6`;
- connector lock to live-verified family code 6;
- no title keyword admission.

Any later broadening beyond family 6 requires separate evidence proving the exact controlled codes/discriminator. Do not silently add family 5.

### 5. Bounded execution

Preserve hard limits:
- page size maximum 100;
- page count maximum 50;
- future end-date server filter;
- pre-call start-date client admission;
- fail closed on pagination metadata drift/incompleteness.

Do not switch to the currently failing Excel route merely to reduce request count without a new live contract test.

### 6. Money

Do not populate PAC `value` or `currency` until the machine-readable source contract exposes a verified amount/currency mapping. A frontend field name alone is insufficient evidence.

## Merge conflict strategy

Likely conflict hotspots:
- `source_registry.py`
- `preload.py`

Resolve semantically against current `main` at integration time:
- preserve every valid source added by parallel cells;
- preserve all unrelated preload/runtime hooks;
- add only the minimal Uruguay composition changes;
- rerun tests after conflict resolution on the **exact resulting head**.

Never choose a whole-file `ours`/`theirs` resolution for either canonical file.

## Required integration tests before runtime promotion

- existing UY_ARCE TENDER tests remain green;
- PAC tests remain green;
- combined fetch stages both signal types under one source identity;
- PAC failure prevents partial cursor advancement;
- TENDER failure prevents PAC-only source commit if composition is atomic;
- repeated PAC snapshot is idempotent;
- source health reports a truthful failure instead of silently dropping PAC;
- full repository Python + mobile Quality succeeds;
- bounded live PAC connector succeeds from the actual deployment network.

## Rollback

Before runtime integration: revert PR #196; no schema/runtime change exists.

After future runtime integration: revert the minimal PAC registry/preload composition commit while retaining the pre-existing `UY_ARCE` TENDER connector and cursor namespace. No PAC rollback should delete or rewrite historical TENDER state.

## Current status

`INTEGRATION-READY CANDIDATE / NO AUTO-MERGE / NO RUNTIME PROMOTION AUTHORIZED BY THIS MANIFEST`
