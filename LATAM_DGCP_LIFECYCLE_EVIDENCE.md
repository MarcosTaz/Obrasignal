# LATAM Next Wave — Dominican Republic DGCP Lifecycle Evidence Addendum

CELL: LATAM_NEXT_WAVE
COUNTRY: Dominican Republic
ISO2: DO
ISO3: DOM
SOURCE: `DO_DGCP` — Dirección General de Contrataciones Públicas / DGCP Open Data
RESEARCHED_AT: 2026-08-25
LAST_UPDATED: 2026-08-25
CANONICALITY: CELL-SCOPED EVIDENCE ADDENDUM. It enriches, but does not replace, canonical registries or `LATAM_NEXT_WAVE_CELL_EVIDENCE.md`.

## RAW / OBSERVED FACTS

1. Official DGCP Swagger exposes `/contratos`, `/procesos`, `/ocds/releases`, `/ocds/releases/all`, `/tablas/procesos` and `/tablas/contratos`.
2. Live `/contratos` machine access succeeded from GitHub Actions on 2026-08-25.
3. Observed contract structural fields:
   - `codigo_contrato`
   - `codigo_proceso`
   - `codigo_unidad_compra`
   - `descripcion`
   - `divisa`
   - `estado_adjudicacion`
   - `estado_contrato`
   - `fecha_adjudicacion`
   - `fecha_creacion_contrato`
   - `metodo_pago`
   - `plazo_pago_factura`
   - `razon_social`
   - `rpe`
   - `unidad_compra`
   - `url_contrato`
   - `valor_contratado`
4. A live contract→process lookup by `codigo_proceso` succeeded. The process record exposes publisher-native `objeto_proceso` and `subobjeto_proceso`, so construction admission does not require keyword inference.
5. The corresponding OCDS identity follows `ocds-6550wx-{codigo_proceso}` for the live-probed adjudicated process.
6. Live `/ocds/releases?ocid=...` for that adjudicated process returned a ReleasePackage containing at least one `award` and one `contract`.
7. Observed lifecycle structural fields:
   - award: `date`, `id`, `items`, `status`, `suppliers`
   - contract: `awardID`, `id`, `period`, `status`, `title`, `value`
8. Official full-history `/tablas/procesos` and `/tablas/contratos` transports return XLSX. The process full-history export exceeded a 64 MiB bounded probe, so blind full-history daily ingestion was rejected.
9. The official tables UI advertises year/semester partitions, but no stable partition URL/API contract was established from the documented API. UI scraping was rejected as a production dependency.
10. The final bounded live gate on the branch passed after the permanent test was reduced to documented/stable transports only.

## INTERPRETATION

The existing OCDS detail hydration is the superior lifecycle route. It already carries tender context plus award/contract state and avoids both:
- an N+1 `/contratos` → `/procesos` lookup strategy; and
- a heavy full-history XLSX join.

A ReleasePackage may contain multiple partial releases for the same OCID. Treating only the first matching release as the hydrated record can lose later tender/lifecycle state. Therefore lifecycle support requires preserving ReleasePackage history and merging non-empty entity fields across releases.

## IMPLEMENTATION

Branch/PR #176 now contains reusable shared-family support:
- `ocds_release_lifecycle.py`
  - `OCDSReleasePackageConnector` preserves all releases for the requested OCID;
  - supports one hydrated OCDS package emitting multiple canonical signals without duplicate network requests;
  - malformed multi-signal output fails closed.
- `dominican_republic_dgcp.py`
  - uses the ReleasePackage connector;
  - preserves compatibility through `fetch_dgcp_processes()` returning active TENDER only;
  - adds `fetch_dgcp_signals()` for TENDER + AWARD + CONTRACT from the same hydration;
  - uses latest release containing tender context rather than blindly choosing the latest partial release;
  - lifecycle is admitted only when publisher-native `mainProcurementCategory == works`;
  - award identity: `{ocid}:award:{award_id}`;
  - contract identity: `{ocid}:contract:{contract_id}`;
  - later partial updates preserve prior non-empty lifecycle fields.

## TEST STATUS

TESTED: YES on branch.

Deterministic coverage includes:
- ReleasePackage history preservation;
- one hydration → multiple canonical signals;
- malformed multi-signal output fail-closed;
- latest tender-containing release selection;
- strict works-only lifecycle admission;
- stable award/contract identities;
- supplier linkage award→contract;
- contract value/currency/period preservation through later partial updates;
- completed tender emits lifecycle but not live TENDER;
- compatibility path remains TENDER-only.

Exact branch head `fe961dd46476dfebdc3cf777a586ac0cb952798b`:
- ObraSignal Quality / Python: SUCCESS.
- ObraSignal Quality / mobile: SUCCESS.
- Dominican Republic DGCP Live Gate: SUCCESS.

## LIVE VALIDATION STATUS

LIVE_VALIDATED: YES for current source contracts and lifecycle presence.
PRODUCTION_PATH_VALIDATED: NO.
RUNTIME_WIRED: NO.
PRODUCTION: NO.

The live gate proves current public machine access and that a real adjudicated DGCP process maps to an OCDS package with award + contract. It does not prove full production-volume completeness, latency, or hydration economics.

## COMMERCIAL DECISION

Lifecycle depth materially improves contractor intelligence: ObraSignal can link works procurement to awarded supplier and contract state/value from the same official source family. The route has substantially better engineering economics than a second bulk-XLSX pipeline.

DECISION: IMPLEMENTED / TESTED / LIVE_VALIDATED ON BRANCH; KEEP GATED FROM RUNTIME.

## CANONICAL REGISTRY NOTE

The current canonical branch record for `DO_DGCP` still declares only `PROCUREMENT_PLAN` + `TENDER`. Under the International Research Consolidation Guard, this addendum intentionally does not perform a whole-file rewrite of `source_registry.py` solely to add lifecycle metadata while parallel cells may be editing the same registry.

Recommended later semantic enrichment:
- capabilities: add `awards`, `contracts`, `lifecycle`;
- signal_types: add `AWARD`, `CONTRACT`;
- adapter: reflect `OCDSReleasePackageConnector` plus the DGCP PACC connector;
- keep `status=planned` until runtime and production completeness gates close.

Stable source identity is the source key `DO_DGCP`. The feature-encoded secondary `source_id=do_dgcp_ocds_pacc` should be normalized during consolidation to a publisher/system identity such as `do_dgcp_open_data`; do not create a second source record.

## CONFLICT

previous finding:
- DGCP evidence originally described award/contract surfaces as publisher capability only, not implemented ObraSignal lifecycle.

new finding:
- live testing proved a real DGCP adjudicated process has structured OCDS awards/contracts and the branch now implements canonical AWARD/CONTRACT normalization using the same hydration.

evidence:
- PR #176 live workflow on 2026-08-25;
- `test_dominican_republic_dgcp_contracts_live.py`;
- `test_dominican_republic_dgcp_lifecycle.py`;
- `test_ocds_release_lifecycle.py`.

likely explanation:
- lifecycle depth was intentionally deferred until the source transport and construction context were live-proven.

recommended canonical resolution:
- enrich the existing `DO_DGCP` record during the controlled International Consolidation Pass; preserve `status=planned` until runtime integration and production-volume completeness are verified.

## BLOCKERS / REMAINING GATES

- production runtime composition is not wired;
- full-window discovery/hydration completeness at production volume remains to be measured;
- source health/freshness behavior for lifecycle signals must be exercised in the actual runtime;
- canonical registry metadata should be enriched via semantic merge, not blind replacement.

## PR REFERENCES

- CODE / EVIDENCE: PR #176.
- RELATED LATAM RESEARCH: #179 Peru, #180 Panama.

## ZERO-LOSS / ZERO-DUPLICATION

- No new country/source identity was created: lifecycle enriches `DO_DGCP`.
- No regional runtime was created.
- No second lifecycle ingestion source was introduced.
- The rejected XLSX/N+1 routes are preserved here as negative evidence so a later cell does not repeat them.
