# Uruguay ARCE PAC — Evidence

CELL: LATAM_NEXT_WAVE
COUNTRY: Uruguay (UY / URY)
SOURCE_IDENTITY: `UY_ARCE` — Agencia Reguladora de Compras Estatales / Compras Estatales
EVIDENCE_DATE: 2026-08-25
CANONICALITY: branch-scoped evidence; canonical source/runtime metadata remains subject to semantic consolidation.

## Decision

`BUILD / IMPLEMENTED + TESTED + LIVE-VALIDATED / INTEGRATION-READY / RUNTIME-GATED`

The PAC is a material early-signal extension of the existing Uruguay source, not a new source.

## Official public contract observed

Public SPA:
- `https://www.comprasestatales.gub.uy/consultaplananual/`
- public config: `assets/config.json`
- configured `apiUrl`: `/consultaplananual`
- effective public API base: `https://www.comprasestatales.gub.uy/consultaplananual`

Machine routes used by the public SPA include:
- paginated procedures: `/api/v1/compra-procedimientos`
- procedure detail: `/api/v1/compra-procedimientos/{id}`
- families: `/api/v1/familias/all`
- family/subfamily/class/subclass catalogue routes.

The SPA query contract includes `codFamilia`, `codSubfamilia`, `codClase`, `codSubclase`, `codArticuloServObra`, `fechaConvocatoriaFinDesde`, planned-period fields, publication fields and modification fields.

## Construction admission

Runtime admission does **not** use title keywords.

Live catalogue response on 2026-08-25 identified:
- family code `6`
- label `6 - CONSTRUCCIONES, MEJORAS Y REPARACIONES EXTRAORDINARIAS`

The implementation fixes this live-verified code in the connector and rejects configuration drift to any other family code. Official ARCE catalogue documentation separately defines an article/service/work discriminator (`ind_art_serv`); this supports the publisher's controlled construction taxonomy but is not required by the current PAC connector.

## Bounded execution

Without the future-date filter, live `codFamilia=6` returned:
- `totalElements=5340`
- `totalPages=1068` at the five-row research page size.

The publisher filter:
- `fechaConvocatoriaFinDesde=2026-08-25`

reduced the live set to:
- `totalElements=825`

The API accepts ISO `YYYY-MM-DD`; `25/08/2026` returned HTTP 400 in the bounded probe.

The production-candidate connector additionally requires `periodoConvFechaIni >= source-local today`, preserving only genuine pre-call signals. Exact-head live execution returned 261 normalized future `PROCUREMENT_PLAN` signals on 2026-08-25.

Hard execution limits:
- `page_size <= 100`
- `max_pages <= 50`
- `timeout <= 120s`
- page number must match request
- `totalPages` must remain stable during snapshot
- incomplete/early-empty page fails closed
- source/country/family identity drift fails closed.

## Signal contract

Canonical branch output:
- source: `UY_ARCE`
- signal_type: `PROCUREMENT_PLAN`
- external identity: `pac:{procedure_id}`
- buyer: PAC purchasing unit, with controlled fallbacks to executing unit/inciso
- target date: planned call-window start
- planned window end: publisher PAC field
- procurement type/subtype preserved
- plan ID/year and buyer codes preserved
- taxonomy: `ARCE_PAC_FAMILY`
- category code: `6`
- contract type: `works`

Rows marked `dadoBaja`, malformed identity/buyer/start-date rows, already-started calls and inverted date windows are excluded.

## Monetary field

The current live JSON search/detail contract observed on 2026-08-25 did not expose a reliable monetary field even though the public frontend model references `montoTotalEstimado`. The connector therefore leaves `value` and `currency` blank. No amount or currency is inferred.

## Negative evidence

The SPA advertises `/api/v1/compra-procedimientos/excel`, but the current production route returned HTTP 404 in live probing. The connector does not use or depend on that export.

Fresh standalone API requests produced inconsistent behavior during early research; reproducing the legitimate public SPA flow with one same-origin session (public page -> public config -> API) produced stable `[200, 200, 200]` search responses and successful detail/catalog calls. The implementation uses that public same-origin session sequence and no authentication or bypass.

## Tests and live validation

At branch HEAD `b82248fe1631840e9691db164c255f3707e78197` during implementation:
- ObraSignal Quality Python: SUCCESS
- ObraSignal Quality mobile: SUCCESS
- Uruguay ARCE PAC live gate: SUCCESS
- live connector normalized 261 future family-6 procurement-plan signals.

Subsequent documentation commits require the normal exact-head gate before final delivery; prior success is not silently transferred to a later HEAD.

Deterministic tests cover:
- stable signal identity
- no keyword requirement
- no synthetic money
- removal/past/malformed/inverted-window rejection
- same-origin bootstrap and official path allowlist
- server-side family/date query construction
- pagination and completeness
- malformed page/page-number/page-count drift
- early empty page
- duplicate identity behavior
- source/country/family identity safety
- bounded configuration limits.

## Rights / production gate

The existing canonical `UY_ARCE` source is already registered with publisher-level legal reuse GREEN and machine access VERIFIED for its OCDS path. This PAC branch does not claim that existing TENDER production status automatically proves the complete PAC production path. PAC remains runtime-gated until canonical integration confirms reuse/attribution applicability, runtime composition and source-health behavior.

## Final branch classification

`SHARED SOURCE DEEPENING / EARLY SIGNAL / IMPLEMENTED / TESTED / LIVE-VALIDATED / INTEGRATION-READY / NOT RUNTIME-INTEGRATED`
