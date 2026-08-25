# LATAM Next Wave — Cell Evidence

CELL: LATAM_NEXT_WAVE
RESEARCHED_AT: 2026-08-25
LAST_UPDATED: 2026-08-25
PURPOSE: preserve cell-scoped evidence and decisions without becoming a competing global source of truth.
CANONICALITY: EVIDENCE ONLY. Canonical market/source/family state remains in the repository registries and later International Consolidation Pass.

## Stable identity map

| Country | ISO2 | ISO3 | Stable source identity |
|---|---|---|---|
| Dominican Republic | DO | DOM | `DO_DGCP` — Dirección General de Contrataciones Públicas / DGCP Open Data API |
| Paraguay | PY | PRY | `PY_DNCP` — Dirección Nacional de Contrataciones Públicas / API v3 |
| Peru | PE | PER | OECE/SEACE Contrataciones Abiertas OCDS publication; canonical source ID not created in this cell |
| Colombia | CO | COL | `CO_SECOP` — SECOP II Open Data |
| Uruguay | UY | URY | `UY_ARCE` — ARCE Compras Estatales OCDS |
| Panama | PA | PAN | PanamaCompra / PanamaCompraenCifras V2; canonical source ID not created in this cell |
| Costa Rica | CR | CRI | SICOP; canonical source ID not created in this cell |
| Mexico | MX | MEX | Compras MX federal platform; canonical source ID not created in this cell |

---

## Dominican Republic — DO / DOM

COUNTRY: Dominican Republic
CELL: LATAM_NEXT_WAVE
PRIMARY_OFFICIAL_SOURCES:
- DGCP Open Data API / Swagger: `https://datosabiertos.dgcp.gob.do/api-dgcp/docs/doc.json`
- API root: `https://datosabiertos.dgcp.gob.do/api-dgcp/v1`
SECONDARY_OFFICIAL_SOURCES:
- DGCP PACC guidance / controlled procurement-object terminology.
SIGNAL_TYPES: `TENDER`, `PROCUREMENT_PLAN` implemented in this branch; publisher also exposes contract/offer/provider surfaces but those are not claimed as implemented signal types.
COVERAGE_SCOPE:
- OCDS discovery via `/ocds/releases/all` and detail hydration via `/ocds/releases?ocid=...`.
- PACC annual planned acquisitions via `/pacc/adquisiciones`.
- PACC article enrichment route `/pacc/articulos` exposes UNSPSC family/class/subclass.
CONSTRUCTION_FILTER:
- TENDER: publisher-native OCDS `tender.mainProcurementCategory == works` and active tender gate.
- PROCUREMENT_PLAN: publisher-controlled `objeto_adquisicion == Obras`; no keyword admission.
ACCESS: public machine-readable API, no auth required in observed live tests.
RIGHTS: Swagger declares Apache-2.0; registry legal reuse remains GREEN.
IDENTITY:
- TENDER: OCDS OCID.
- PROCUREMENT_PLAN: stable composite `uid_pacc:id_adquisicion`.
FRESHNESS:
- Publisher documentation states warehouse refresh at 00:00, 07:00, 14:00, 21:00 Dominican time.
- PACC endpoint is treated as annual snapshot because no row-level incremental cursor was observed.
EARLY_SIGNAL_DEPTH: HIGH — PACC carries buyer, description/finalidad, planned start date, procurement method and budgeted value; article endpoint carries UNSPSC.
AWARD_CONTRACT_DEPTH: PUBLISHER SURFACE EXISTS; not implemented/validated as ObraSignal lifecycle output in this cell.
TECHNICAL_ROUTE:
- Reuse existing `OCDS_PAGE_API` family for tenders.
- Separate source-specific PACC snapshot connector emits canonical `PROCUREMENT_PLAN` into the existing Signal contract; no LATAM runtime silo.
COMMERCIAL_ASSESSMENT: high-value early-signal addition with low framework cost because tender transport reuses OCDS and PACC object type is publisher-controlled.
IMPLEMENTATION_STATUS: IMPLEMENTED ON PR #176; registry intentionally `planned` / runtime gated.
TEST_STATUS:
- deterministic unit/regression tests present;
- full repository Python quality passed on branch heads during development.
LIVE_VALIDATION_STATUS:
- GitHub Actions live gate passed for OCDS discovery+detail;
- GitHub Actions live gate passed for PACC acquisitions and PACC article taxonomy.
- Observed PACC acquisition fields: `codigo_unidad_compra`, `descripcion`, `dirigido_mipymes`, `dirigido_mipymes_mujeres`, `fecha_inicio_proceso_compra`, `finalidad`, `id_adquisicion`, `modalidad_adquisicion`, `objeto_adquisicion`, `uid_pacc`, `unidad_compra`, `valor_presupuestado`, `version`.
- Observed PACC article fields: `cantidad`, `clase_unspsc`, `codigo_unidad_compra`, `descripcion`, `familia_unspsc`, `id_adquisicion`, `id_business_item_line`, `precio_total_estimado`, `precio_unitario_estimado`, `subclase_unspsc`, `uid_pacc`, `unidad_compra`, `unidad_medida`.
BLOCKERS:
- runtime not enabled;
- tender full-window production completeness and sustainable hydration volume still need production-path validation;
- PACC snapshot volume/completeness must be proven at production scale before registry status can become ready.
FINAL_CLASSIFICATION: SHARED COVERAGE / IMPLEMENTED BUT GATED.
EVIDENCE_REFS: official Swagger/API; live GitHub Actions logs on PR #176; repository tests.
PR_REFS: #176.
LAST_LIVE_VALIDATED_AT: 2026-08-25.
SOURCE_LAST_OBSERVED_AT: 2026-08-25.

CONFLICT — previous finding: PR #176 initially documented PACC as out of scope and `DO_DGCP.machine_access` as not live-validated.
new finding: subsequent same-cell live tests proved OCDS and PACC public machine access and justified a bounded PACC `PROCUREMENT_PLAN` implementation.
evidence: successful dedicated DGCP live workflow and observed PACC field contracts on 2026-08-25.
likely explanation: deliberate staged validation; the earlier statement predated the PACC live probe.
recommended canonical resolution: preserve the chronology in this evidence file; keep registry `machine_access=VERIFIED` but `status=planned` until production runtime/completeness gates are closed.

---

## Paraguay — PY / PRY

PRIMARY_OFFICIAL_SOURCES: DNCP API v3 / OCDS.
SIGNAL_TYPES: registry declares `PROCUREMENT_PLAN`, `TENDER`, `AWARD`, `CONTRACT`.
COVERAGE_SCOPE: search, incremental, record hydration, awards/contracts/plans/amendments capability metadata.
CONSTRUCTION_FILTER: publisher-side works filter plus active tender validation.
ACCESS: production OAuth/token route; anonymous access only publisher-allowed testing mode.
RIGHTS: open-data publication; registry GREEN.
IDENTITY: OCDS OCID.
FRESHNESS: incremental bounded windows.
EARLY_SIGNAL_DEPTH: HIGH in source capability.
AWARD_CONTRACT_DEPTH: HIGH in source capability.
TECHNICAL_ROUTE: existing shared `OCDS_PAGE_API` family and country config.
COMMERCIAL_ASSESSMENT: strong reusable regional source, already implemented.
IMPLEMENTATION_STATUS: IMPLEMENTED / ready / opt-in runtime path already exists.
TEST_STATUS: existing connector tests; prior PR quality passed.
LIVE_VALIDATION_STATUS: prior implementation live-validated search + record hydration.
BLOCKERS: production credentials/environment configuration for runtime use.
FINAL_CLASSIFICATION: IMPLEMENTED / SKIP WITH EVIDENCE.
PR_REFS: #101.
LAST_UPDATED: 2026-08-25.

---

## Peru — PE / PER

PRIMARY_OFFICIAL_SOURCES:
- OECE/SEACE Contrataciones Abiertas OCDS portal/API/bulk publication.
- OECE open-data/PAC surfaces.
SIGNAL_TYPES: publisher evidence supports `PROCUREMENT_PLAN`, `TENDER`, `AWARD`, `CONTRACT`; no ObraSignal source record was added by this cell.
COVERAGE_SCOPE: daily OCDS/API/bulk publication plus PAC and SEACE early procurement surfaces.
CONSTRUCTION_FILTER: should use publisher-native OCDS/taxonomy when machine route is available; no keyword-only implementation approved.
ACCESS: current GitHub-hosted live probe in related PR returned HTTP 403 on official machine endpoint.
RIGHTS: related PR cites OCP Data Registry CC BY 4.0 evidence; canonical legal gate must be rechecked at implementation time.
IDENTITY: OCDS OCID expected; no new source identity minted here to avoid duplication.
FRESHNESS: official publication evidence indicates daily publication.
EARLY_SIGNAL_DEPTH: VERY HIGH — PAC plus future-contract/requirements/interest surfaces.
AWARD_CONTRACT_DEPTH: HIGH in publisher publication.
TECHNICAL_ROUTE: prefer existing OCDS family when access gate clears; no bespoke Peru framework.
COMMERCIAL_ASSESSMENT: highest-priority new LATAM market in the research queue, but current machine-access gate blocks safe implementation.
IMPLEMENTATION_STATUS: RESEARCHED / TECHNICALLY ROUTED / GATED; no production connector.
TEST_STATUS: related PR live access probe performed.
LIVE_VALIDATION_STATUS: machine route returned HTTP 403 from hosted runner; no bypass attempted.
BLOCKERS: stable permitted machine access from production environment.
FINAL_CLASSIFICATION: SHARED COVERAGE / GATED.
PR_REFS: #179 RELATED PARALLEL WORK.
LAST_LIVE_VALIDATED_AT: 2026-08-25 (access gate observation).

---

## Colombia — CO / COL

PRIMARY_OFFICIAL_SOURCES: SECOP II Open Data, dataset `p6dx-8zbt` on datos.gov.co.
SIGNAL_TYPES: registry declares `PROCUREMENT_PLAN`, `TENDER`, `AWARD`, `CONTRACT`.
COVERAGE_SCOPE: Socrata/SODA search, incremental sync, plans, awards, contracts, suppliers.
CONSTRUCTION_FILTER: `estado_de_apertura_del_proceso = Abierto` plus publisher field `tipo_de_contrato = Obra`.
ACCESS: public Socrata API.
RIGHTS: registry GREEN.
IDENTITY: Socrata row/system identity and procurement process identity.
FRESHNESS: technical cursor uses Socrata `:updated_at` + `:id`.
EARLY_SIGNAL_DEPTH: high source capability.
AWARD_CONTRACT_DEPTH: high source capability.
TECHNICAL_ROUTE: existing reusable Socrata adapter + SECOP country configuration.
COMMERCIAL_ASSESSMENT: core LATAM implemented market.
IMPLEMENTATION_STATUS: IMPLEMENTED / ready / opt-in runtime.
TEST_STATUS: existing tests and prior full quality validation.
LIVE_VALIDATION_STATUS: prior implementation live-validated official API.
BLOCKERS: runtime opt-in/deployment config only.
FINAL_CLASSIFICATION: CORE/BUILD / IMPLEMENTED / SKIP WITH EVIDENCE.
PR_REFS: #100 (supersedes #98 decomposition PR).

---

## Uruguay — UY / URY

PRIMARY_OFFICIAL_SOURCES: ARCE Compras Estatales OCDS RSS/record/release publication.
SIGNAL_TYPES: ObraSignal implementation currently declares `TENDER`; publisher datasets are richer but are not silently promoted to extra signal types.
COVERAGE_SCOPE: RSS event index, monthly recovery, record indexes and release hydration.
CONSTRUCTION_FILTER: implemented source-specific lifecycle/actionability path; no new regional fork.
ACCESS: public official RSS/record/release endpoints.
RIGHTS: registry GREEN under Uruguay open-data licence with attribution.
IDENTITY: purchase/record/release identities with deterministic event cursor.
FRESHNESS: monotonic `(pubDate, guid)` cursor and monthly recovery for old cursors.
EARLY_SIGNAL_DEPTH: publisher PAC exists; not implemented as canonical `PROCUREMENT_PLAN` in current source adapter.
AWARD_CONTRACT_DEPTH: publisher provides award/contract-related data; not declared as implemented signal types in current registry.
TECHNICAL_ROUTE: source-specific ARCE adapter; intentionally outside generic OCDS page family because transport semantics differ.
COMMERCIAL_ASSESSMENT: useful implemented market; deepen only through separate tested lifecycle work.
IMPLEMENTATION_STATUS: IMPLEMENTED / ready / opt-in runtime.
TEST_STATUS: prior source and runtime tests passed.
LIVE_VALIDATION_STATUS: prior official RSS→record→release contract validated.
BLOCKERS: additional signal types require separate implementation/test evidence.
FINAL_CLASSIFICATION: IMPLEMENTED / SKIP WITH EVIDENCE.
PR_REFS: #102.

---

## Panama — PA / PAN

PRIMARY_OFFICIAL_SOURCES:
- PanamaCompra / PanamaCompraenCifras V2.
- PanamaenObras public-infrastructure lifecycle surface.
SIGNAL_TYPES: potential `TENDER`, `AWARD`, `CONTRACT`, and high-value `CAPITAL_PROJECT`; none newly implemented by this cell.
COVERAGE_SCOPE: current V2 portal advertises OCDS API and data downloads; indexed process pages expose OCIDs/RecordPackage actions; PanamaenObras adds infrastructure-project depth.
CONSTRUCTION_FILTER: should rely on publisher-native OCDS/OC4IDS/project structure when exact machine contract is proven.
ACCESS: related live probe hit TLS certificate-chain validation failure on standard GitHub runner.
RIGHTS: current V2 reuse/licence/attribution still requires explicit confirmation.
IDENTITY: OCDS/OC4IDS identities expected; no source record minted before route is proven.
FRESHNESS: current V2 publication exists, but exact incremental/completeness semantics not yet proven.
EARLY_SIGNAL_DEPTH: potentially high via infrastructure/project lifecycle.
AWARD_CONTRACT_DEPTH: potentially high.
TECHNICAL_ROUTE: reopen through shared OCDS/OC4IDS infrastructure if gates clear; no Panama-specific runtime silo.
COMMERCIAL_ASSESSMENT: stronger than previous HOLD assumption; worth targeted reopening.
IMPLEMENTATION_STATUS: RESEARCHED / PREPARE / GATED.
TEST_STATUS: bounded live TLS/machine-access probe in related PR.
LIVE_VALIDATION_STATUS: source surface observed, but standard TLS verification failed; no `verify=False`, path guessing or bypass.
BLOCKERS: valid production TLS route; exact public API/bulk endpoints; completeness semantics; current reuse rights; native construction-selection proof.
FINAL_CLASSIFICATION: PREPARE / REOPEN HOLD.
PR_REFS: #180 RELATED PARALLEL WORK.

CONFLICT — previous finding: canonical market registry HOLD rationale assumed no sufficiently stable canonical automated ingestion route.
new finding: current V2 surface explicitly advertises OCDS API/data download and current process pages expose OCDS identities, but live machine access remains gated by TLS/endpoint/rights proof.
evidence: PR #180 current portal evidence and live TLS failure.
likely explanation: publisher platform evolved after the earlier classification.
recommended canonical resolution: keep HOLD from becoming BUILD, but mark for targeted reopen until the current machine/rights gates are resolved.

---

## Costa Rica — CR / CRI

PRIMARY_OFFICIAL_SOURCES: SICOP open-data/reporting and acquisition-plan surfaces.
SIGNAL_TYPES: potential tender/award/contract/plan data; no source implementation created.
COVERAGE_SCOPE: current portal exposes open-data modules for awards, suppliers, competitions, goods/services, contracts and acquisition planning.
CONSTRUCTION_FILTER: publisher UNSPSC/search structures exist, but no stable low-burden construction ingestion contract was proven in this cell.
ACCESS: public portal/open-data surfaces; exact production API contract not sufficiently established.
RIGHTS: legal framework supports open formats/API availability, but source-specific commercial reuse contract was not promoted to canonical GREEN by this cell.
IDENTITY: no new source ID minted.
FRESHNESS: not sufficiently proven for an implementation decision.
EARLY_SIGNAL_DEPTH: moderate/potential.
AWARD_CONTRACT_DEPTH: moderate/potential.
TECHNICAL_ROUTE: no bespoke connector justified under current 100-hour test.
COMMERCIAL_ASSESSMENT: technically richer than an older 'no open data' assumption, but small market + local competition + engineering economics remain unfavorable relative to Peru/DR/Panama.
IMPLEMENTATION_STATUS: RESEARCHED; no code.
TEST_STATUS: none for a connector because no connector justified.
LIVE_VALIDATION_STATUS: portal/source research only, not production-path validation.
BLOCKERS: economics and lack of a clearly superior low-maintenance machine route.
FINAL_CLASSIFICATION: REMOVE CURRENT PHASE.

CONFLICT — previous finding: older external research could be read as 'SICOP has no open data'.
new finding: current SICOP exposes open-data and acquisition-plan surfaces and the legal framework contemplates open formats/APIs.
evidence: current SICOP/CGR research on 2026-08-25.
likely explanation: temporal change / stale prior publication.
recommended canonical resolution: do not use 'no open data' as the removal rationale; preserve REMOVE on commercial/engineering priority grounds instead.

---

## Mexico — MX / MEX

PRIMARY_OFFICIAL_SOURCES: Compras MX federal procurement platform.
SECONDARY_OFFICIAL_SOURCES: state-level OCDS initiatives may exist, but they are not substitutes for federal coverage.
SIGNAL_TYPES: potential tender/award/contract; no implementation created.
COVERAGE_SCOPE: federal platform is active in 2026; stable public incremental federal machine ingestion was not proven in this cell.
CONSTRUCTION_FILTER: unresolved until a canonical machine route is established.
ACCESS: current public user-facing platform exists; no verified federal public incremental API in this research pass.
RIGHTS: not promoted because machine publication route itself remains unresolved.
IDENTITY: no new source ID minted.
FRESHNESS: unresolved for machine ingestion.
EARLY_SIGNAL_DEPTH: potentially high by market size, but fragmented.
AWARD_CONTRACT_DEPTH: potentially high.
TECHNICAL_ROUTE: avoid substituting one state OCDS feed for national/federal coverage; no fragmented state-by-state framework now.
COMMERCIAL_ASSESSMENT: very large TAM but high fragmentation and engineering/maintenance burden.
IMPLEMENTATION_STATUS: RESEARCHED / HOLD.
TEST_STATUS: no connector test because no stable federal route was identified.
LIVE_VALIDATION_STATUS: current federal platform existence verified; machine route not validated.
BLOCKERS: stable official federal live/incremental route and proof that commercial value does not require a costly fragmented state strategy.
FINAL_CLASSIFICATION: HOLD / DEFER.

---

## Cross-cell duplication and reuse check

RELATED PARALLEL/PR WORK FOUND:
- #179 Peru OECE shared OCDS gate — do not duplicate.
- #180 Panama V2 reopen gate — do not duplicate.
- #101 Paraguay DNCP reusable OCDS implementation — reuse.
- #100 Colombia SECOP II reusable Socrata implementation — reuse.
- #102 Uruguay ARCE implementation — reuse; do not force it into the wrong generic transport family.
- #159 canonical shared-source-family architecture — DGCP tender route extends its existing `OCDS_PAGE_API`; no LATAM family fork.

ZERO-RUNTIME-FORK RESULT: PASS. No Africa/MENA/LATAM runtime was created. DGCP uses canonical connector/Signal contracts.
ZERO-DUPLICATION RESULT: PASS WITH CONSOLIDATION NOTES. No new Peru/Panama/Costa Rica/Mexico source records were created; existing PY/CO/UY sources are referenced, not duplicated.
ZERO-SILENT-CONFLICT RESULT: PASS. Temporal/semantic conflicts identified above are explicit.
ZERO-LOSS RESULT: PASS SUBJECT TO PR #176 MERGE. This file preserves the cell findings, decisions, live-test basis, related PRs and unresolved gates even if ephemeral chat context disappears.
