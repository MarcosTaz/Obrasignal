# LATAM Next Wave — Canonical Integration Manifest

CELL: LATAM_NEXT_WAVE
COUNTRIES: Dominican Republic (DO/DOM), Paraguay (PY/PRY), Peru (PE/PER), Colombia (CO/COL), Uruguay (UY/URY), Panama (PA/PAN), Costa Rica (CR/CRI), Mexico (MX/MEX)
LAST_UPDATED: 2026-08-25
CANONICALITY: integration manifest only; not an alternate global portfolio.

SOURCE RECORDS ADDED:
- `DO_DGCP` on PR #176, planned/runtime-gated. Stable identity is DGCP Open Data API publication, not the current endpoint URL.

SOURCE RECORDS UPDATED:
- `DO_DGCP` evidence state now reflects live-verified public machine access and canonical signal capability `PROCUREMENT_PLAN` + `TENDER`, while `status=planned` preserves the runtime gate.
- No duplicate source record created for PY_DNCP, CO_SECOP or UY_ARCE.
- No source record created for Peru/Panama/Costa Rica/Mexico until their current gates justify one.

SHARED FAMILIES:
- Existing `OCDS_PAGE_API` extended with `DO_DGCP` for the tender route.
- PACC is source-specific configuration/transport emitting the canonical Signal contract; it does not create a LATAM runtime/family silo.
- Related family architecture: PR #159.

CODE PRs:
- #176 — Dominican Republic DGCP OCDS + PACC implementation, tests and live gate.
- Existing reused implementations: #101 Paraguay, #100 Colombia, #102 Uruguay.

RESEARCH PRs:
- #179 — Peru OECE machine-access gate.
- #180 — Panama V2 machine/TLS/reuse gate.
- Cell-scoped consolidated evidence is preserved in `LATAM_NEXT_WAVE_CELL_EVIDENCE.md` on #176.

CANONICAL FILES TO UPDATE LATER:
- Global market portfolio / international scope only during the dedicated International Consolidation Pass.
- Market-scope registry may need semantic reconciliation for Panama reopen state and Dominican Republic once production-path gates close.
- Source registry should only be promoted from `planned` to `ready` for `DO_DGCP` after production-path completeness/runtime validation.
- Shared-family registry already receives the minimal `DO_DGCP` membership change in #176; later consolidation must check for concurrent edits before merge.

CONFLICTS:
1. Dominican Republic machine access/PACC scope changed during this same cell after live validation. Chronology and resolution are recorded in the evidence file.
2. Panama prior HOLD premise is partially stale because current V2 advertises OCDS API/downloads, but live production-path proof is still incomplete. Do not silently promote to BUILD.
3. Costa Rica older 'no open data' language is stale; current removal rationale should be economics/engineering priority, not absence of data.

DEPENDENCIES:
- #176 depends only on existing canonical contracts/families already present on its real base; it does not require #179 or #180 to merge.
- Peru #179 and Panama #180 are RELATED PARALLEL WORK, not code dependencies.
- Future consolidation must compare the then-current `source_registry.py` and `shared_source_families.py` before applying registry changes from this PR.

BLOCKERS:
- DO_DGCP runtime/prod: full-window production completeness, sustainable OCDS hydration volume, production-scale PACC snapshot completeness/runtime integration.
- Peru: official machine route currently returned HTTP 403 in hosted live probe; no bypass permitted.
- Panama: TLS chain / exact machine endpoint / rights / completeness gates.
- Mexico: stable official federal incremental route not proven.
- Costa Rica: current 100-hour commercial/engineering test not passed.

MERGE RISKS:
- Moderate conflict risk on `source_registry.py` and `shared_source_families.py` because parallel international cells may touch the same canonical registries.
- Mitigation: #176 changes are line-local; evidence/manifest are new cell-scoped files. Rebase/semantic merge must preserve concurrent source entries and family members.
- Do not resolve registry conflicts by taking either whole-file side.

SAFE INTEGRATION NOTES:
1. Merge/rebase shared contract/family changes first if another PR changed `ocds_adapter.py` or `OCDS_PAGE_API` semantics.
2. Preserve every existing source registry entry from both sides; add/enrich `DO_DGCP` semantically rather than replacing the file.
3. Preserve every existing family member from both sides; union memberships only after duplicate/source-fitness checks.
4. Keep `DO_DGCP.status=planned` unless production-path validation evidence newer than this manifest explicitly closes the gate.
5. Do not create Peru/Panama duplicate source IDs during global consolidation; inspect #179/#180 first.
6. Do not alter `master_execution_queue.py` as part of this cell's merge.
7. Run full global repository tests after conflict resolution, not only the source-specific tests.

NO-MERGE STATEMENT:
- This manifest does not authorize automatic merge of #176 or any related PR.
- A later International Consolidation Pass must reconcile concurrent canonical registry edits and current evidence before global portfolio promotion.

ZERO-LOSS TEST: PASS — country/source findings, decisions, temporal conflicts, tests, live basis and PR references are persisted in repository evidence.
ZERO-DUPLICATION TEST: PASS WITH MERGE CHECK — no duplicate PY/CO/UY records created; PE/PA/CR/MX records intentionally deferred; consolidation must check parallel PRs before minting IDs.
ZERO-SILENT-CONFLICT TEST: PASS — known contradictions are explicitly recorded.
ZERO-RUNTIME-FORK TEST: PASS — one Signal model, one connector architecture, one runtime path retained.
