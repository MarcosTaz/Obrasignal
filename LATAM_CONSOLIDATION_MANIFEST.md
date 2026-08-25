# LATAM Next Wave — Consolidation Manifest

Status: integration candidate; no automatic merge.

## CELL

LATAM NEXT WAVE / controlled international consolidation pass.

## COUNTRIES

- Dominican Republic — implementation consolidated; runtime composer implemented; production activation gated.
- Paraguay — existing canonical implementation retained; no duplicate source/code copied.
- Peru — machine access gated (HTTP 403); no production connector promoted here.
- Colombia — existing canonical implementation retained; no duplicate source/code copied.
- Uruguay — PAC early signals consolidated and atomically composed with existing RSS runtime.
- Panama — TLS/current-contract/reuse gates retained; no production connector promoted here.
- Costa Rica — remove current phase; no engineering added.
- Mexico — hold/defer; no engineering added.

## SOURCE RECORDS ADDED / UPDATED

- `DO_DGCP` — one canonical Dominican source identity, `source_id=do_dgcp_open_data`; remains `status=planned`; metadata truthfully exposes `PROCUREMENT_PLAN`, `TENDER`, `AWARD`, `CONTRACT`.
- `UY_ARCE` — existing single Uruguay source identity enriched for `PROCUREMENT_PLAN` without creating `UY_ARCE_PAC`.
- No duplicate records added for Paraguay, Colombia, Peru, Panama, Costa Rica or Mexico.

## SHARED FAMILIES

- Existing `OCDS_PAGE_API` reused for `DO_DGCP`.
- Reusable `ocds_release_lifecycle.py` preserves partial OCDS releases and supports one hydration -> multiple lifecycle signals.
- No LATAM-specific runtime family or regional runtime silo created.

## CONSOLIDATED CODE

- `dominican_republic_dgcp.py` — DGCP OCDS discovery/hydration and `TENDER` / `AWARD` / `CONTRACT` normalization.
- `dominican_republic_dgcp_pacc.py` — bounded DGCP PACC `PROCUREMENT_PLAN` snapshot with publisher-controlled `Obras` admission.
- `dominican_republic_dgcp_runtime.py` — one-source atomic/composite runtime state for OCDS progress + daily PACC snapshot scheduling.
- `ocds_release_lifecycle.py` — reusable ReleasePackage lifecycle normalization.
- `uruguay_arce_pac.py` — ARCE PAC construction early signals.
- `uruguay_arce_runtime.py` — atomic RSS cursor + PAC snapshot composition.
- `ocds_adapter.py` — official DGCP envelope support.
- `preload.py` — intentionally routes `UY_ARCE` through the Uruguay composer only; Dominican activation is not wired.

## DOMINICAN LIVE ECONOMICS / PRODUCTION GATE

Observed on 2026-08-25 through bounded GitHub-runner probes against the official DGCP API:

- PACC 2026 contained `48,795` acquisitions.
- `limit=100` required `488` pages and is unsuitable per ordinary sync.
- The official endpoint accepted `limit=1000`, reducing the same snapshot to `49` pages.
- A complete 49-page snapshot finished in `9.641 s` on the runner and normalized to `134` unique future works plans; every retained signal was publisher-classified `Obras` and had a future/current target date.
- The PACC connector now validates official top-level `page`, `limit`, `pages`, `totalResults` metadata, stable totals, calculated page count and final fetched-row completeness when that metadata is present.
- The Dominican runtime cursor stores OCDS progress plus the last successful PACC snapshot date in one opaque source cursor. PACC is therefore due at most once per Dominican local calendar day; no second source cursor is created.
- If PACC is due and fails after OCDS fetch, no observation is returned and the newly discovered OCDS cursor cannot be staged.
- The canonical runtime projection can carry all four signal types while the legacy compatibility projection contains only `TENDER`.

Production activation is deliberately **not** promoted:

- Current OCDS discovery still discovers OCIDs before construction classification and may require detail hydration to establish `tender.mainProcurementCategory=works` and lifecycle state.
- A bounded sample observed hundreds of discovery candidates across a short window, while the current connector intentionally caps detail hydrations per window.
- An attempted official `/procesos` date-window prefilter was not adopted: the live API returned HTTP/API success but `payload.content=None` for the tested bounded date window, so it did not prove a safe replacement discovery contract.
- Therefore OCDS hydration economics/completeness under production volume remain unproven. `DO_DGCP` stays `status=planned`, is not wired in `preload.py`, and retains `runtime_not_enabled` as a production gate.

This is a classified source/runtime gate, not an implementation-success claim.

## URUGUAY RUNTIME SAFETY

- No new runtime fork.
- `UY_ARCE` remains the only canonical Uruguay source identity and preserves its existing durable RSS cursor.
- PAC is composed atomically with the RSS tender fetch: both transports must succeed before one staged source observation is created.
- `stage_source_sync("UY_ARCE", ...)` receives `TENDER + PROCUREMENT_PLAN`; legacy `fetch_base` receives `TENDER` only.
- If PAC fails after RSS fetch, the new RSS cursor is not staged and cannot advance silently.
- There is no second Uruguay source cursor.

## CODE PRs

- PR #197 — this consolidation candidate.
- Source provenance includes tested implementation work behind PR #176 (Dominican Republic) and PR #196 (Uruguay PAC); overlapping source code must not later be merged wholesale on top of this consolidation.

## RESEARCH PRs

- PR #179 — Peru machine-access gate; related parallel evidence, not a code dependency.
- PR #180 — Panama V2/TLS gate; related parallel evidence, not a code dependency.

## CANONICAL FILES TO UPDATE LATER

- Any broader global market/portfolio summaries should be semantically reconciled in the dedicated International Consolidation Pass.
- Do not replace global registries, architecture contracts or Master Execution Queue wholesale from country branches.

## CONFLICTS

- Dominican machine access moved from early research uncertainty to live-verified public access, but production readiness did **not** follow automatically; source remains planned because production-volume hydration is not proven.
- Uruguay PAC evolved from staged code to tested atomic runtime composition under the existing `UY_ARCE` identity; old text describing PAC as unwired is superseded by this manifest.
- Panama/Costa Rica chronology and rationale remain preserved in the cell evidence; do not silently rewrite earlier observations.

## DEPENDENCIES

- No unmerged LATAM country PR is a runtime dependency of PR #197.
- Peru/Panama research PRs are related parallel work only.

## BLOCKERS / GATES

- Dominican Republic: OCDS production-volume hydration/completeness gate; not a machine-access gate.
- Peru: official machine route returned HTTP 403 in the tested runner environment.
- Panama: TLS chain/current API-contract/reuse gates.

## MERGE RISKS

- `source_registry.py`, `shared_source_families.py` and `preload.py` are shared integration surfaces. Resolve future conflicts semantically; never take an entire file as `ours` or `theirs`.
- Do not merge original Dominican/Uruguay implementation PRs wholesale after this consolidation if their overlapping code has already been reconciled here.
- Do not promote `DO_DGCP` to `ready` merely because its runtime composer exists.

## SAFE INTEGRATION NOTES

- One source identity per publisher/system is preserved.
- No regional runtime fork exists.
- Source-specific deterministic tests live beside the connectors/composers.
- Temporary forensic promotion probes were removed after measurements; they are not part of the permanent test suite.
- `master_execution_queue.py` remains untouched.

## EXACT-HEAD QUALITY

Final tested PR head before this documentation-only result stamp: `4ae0703c98e5c9700ecdc59c9d13d398c81ff774`.
ObraSignal Quality run `32845527544`:

- exact revision guard: SUCCESS;
- Python compile: SUCCESS;
- full repository Python suite: `725 passed, 2 skipped, 2 pre-existing warnings`;
- mobile install: SUCCESS;
- Expo Doctor: SUCCESS;
- critical detail wiring: SUCCESS;
- Expo bundle smoke: SUCCESS.

This final documentation-only stamp records the completed run; it does not change executable code or test contracts.

## ZERO-LOSS / ZERO-DUPLICATION / ZERO-SILENT-CONFLICT / ZERO-RUNTIME-FORK

- ZERO-LOSS: cursor advancement is fail-closed for staged global sources; Uruguay and Dominican composers prevent snapshot failure from silently advancing their incremental cursor when the snapshot is due.
- ZERO-DUPLICATION: `UY_ARCE` and `DO_DGCP` each remain one logical source identity; no PAC pseudo-source records are created.
- ZERO-SILENT-CONFLICT: superseded runtime/research assumptions are recorded above instead of overwritten silently.
- ZERO-RUNTIME-FORK: shared `preload.py` / `source_runtime.py` path remains canonical; no LATAM runtime silo is introduced.

## NO-MERGE STATEMENT

No automatic merge is authorized. PR #197 remains an integration candidate. Merge is a separate explicit decision.

## ROLLBACK

Revert PR #197. No schema migration, second source identity, regional runtime, deployment setting or Master Execution Queue mutation is introduced by this consolidation.
