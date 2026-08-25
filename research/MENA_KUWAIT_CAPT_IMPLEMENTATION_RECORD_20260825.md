# ObraSignal — MENA Kuwait CAPT implementation record

RESEARCHED_AT: 2026-08-25
LAST_LIVE_VALIDATED_AT: pending exact-head CI
SOURCE_LAST_OBSERVED_AT: 2026-08-25
CELL: MENA
COUNTRY: Kuwait
ISO2: KW
ISO3: KWT

## Scope

LIMITED HIGH-VALUE SLICE: current public tenders listed by Kuwait's Central Agency for Public Tenders (CAPT), construction/public-works rows only.

This does not automate tender-document purchase, authenticated bidder functions or the full CAPT lifecycle. The separately published annual procurement plan is preserved as an enrichment candidate of the same source identity, not implemented in v0.

## Stable source identity

Registry candidate key: `KW_CAPT`
Stable source id: `kw_capt_public_procurement`
Publisher/system: Central Agency for Public Tenders (CAPT)
Primary official source: `https://capt.gov.kw/ar/tenders/opening-tenders/`

Stable signal identity is the publisher tender number shown under `الرقم`. URL is not identity.

## Observed facts

On 2026-08-25 the main CAPT public open-tender page exposed current records dated 23 August 2026 with tender number, buyer, subject, request date, bid deadline, preliminary-meeting date, type, price and bid bond. Current construction examples included `6/2025/2026` for maintenance/restoration/building/construction works at Civil Aviation sites and multiple Ministry of Electricity/Water tenders for overhead-line installation/maintenance with related civil works.

The page is publicly readable; only purchase of tender documents is explicitly restricted to registered companies.

CAPT also publishes `الخطة السنوية للشراء للسنة المالية 2027/2026`. Prior CAPT rules require public entities to publish schedules of upcoming tenders/prequalifications under annual plans at least 90 days before launch. That is a valuable future `PROCUREMENT_PLAN` enrichment but is intentionally not conflated with this TENDER connector.

## Technical route

OFFICIAL CAPT OPEN-TENDER HTML -> labelled publisher-field parse -> bounded pagination -> native tender-number dedupe -> strong physical-works filter -> Arabic date normalization -> canonical TENDER -> canonical Signal-store test.

Transport/source-contract failure raises an explicit source error and is never interpreted as zero opportunities.

## Construction filter

The v0 filter uses strong Arabic/English physical-works expressions: construction works, civil works, building works, road/bridge works, renovation/restoration and explicit building construction/rehabilitation patterns. Generic maintenance/services are insufficient.

## Access / rights

ACCESS: public unauthenticated listing HTML.
SOURCE STATE: AVAILABLE at observation time.
MACHINE ACCESS: technically proven only after exact-head live CI.
RIGHTS: YELLOW / LEGAL REVIEW REQUIRED. Public readability is not treated as commercial redistribution permission.

No registration/login is used. Authenticated tender-document purchase is outside scope.

## Implementation state

RESEARCHED: YES
TECHNICALLY_PROVEN: pending exact-head live CI
IMPLEMENTED: YES
TESTED: pending exact-head CI
LIVE_VALIDATED: pending exact-head live CI
PRODUCTION_PATH_VALIDATED: NO
GATED: YES
RUNTIME_ENABLED: NO
PRODUCTION: NO

## Conflict record

CONFLICT — PR #173 Kuwait TECH LAB vs concrete public CAPT implementation

previous finding: Kuwait had strong statutory annual-plan potential but production data access remained unresolved; market remained TECH LAB.

new finding: the main CAPT public open-tender listing is machine-readable enough for a bounded current-tender connector, while commercial reuse remains unresolved. The annual plan also exists publicly but is not yet normalized.

recommended canonical resolution: preserve #173; after green CI classify `KW_CAPT` as IMPLEMENTED / TESTED / LIVE_VALIDATED / GATED for TENDER, and retain PROCUREMENT_PLAN as future enrichment of the same source.

## Duplication / family check

Repository/PR search found no competing Kuwait CAPT implementation before branch creation. No GCC family is asserted: CAPT's Arabic labelled-card structure and semantics differ from Oman Esnad, Qatar Ashghal and UAE MoF DPP.

## Canonical Integration Manifest

CELL: MENA
COUNTRIES: Kuwait (KW / KWT)
SOURCE RECORDS ADDED: cell-scoped candidate `KW_CAPT` / `kw_capt_public_procurement`
SOURCE RECORDS UPDATED: none
SHARED FAMILIES: none
CODE PRs: implementation PR from `feature/kw-capt-public-tenders-v0`
RESEARCH PRs: historical evidence PR #173
CANONICAL FILES TO UPDATE LATER: `source_registry.py` via International Consolidation Pass; use one `KW_CAPT` source and enrich later with annual-plan/award capabilities if technically proven
CONFLICTS: PR #173 TECH LAB vs later public-list technical proof; explicit above
DEPENDENCIES: none; branch based on real main SHA `52e011083545a2e69526cd8e0a294cfb61682884`
BLOCKERS: commercial reuse rights not GREEN; runtime absent
MERGE RISKS: low for new files; canonical registry deferred
SAFE INTEGRATION NOTES: search `KW_CAPT` / `kw_capt_public_procurement`, append/enrich one canonical source record with country KWT, TENDER capability, rights YELLOW, status planned and adapter `KuwaitCAPTConnector`. Do not create a second CAPT source when annual-plan support is added.

## Required zero-* checks

ZERO-LOSS: PASS if this record + code PR are retained.
ZERO-DUPLICATION: PASS at branch creation; recheck consolidation.
ZERO-SILENT-CONFLICT: PASS.
ZERO-RUNTIME-FORK: PASS.

## Stop status

This is a fifth-win candidate. It does not complete the MENA cell until remaining Saudi Arabia, Morocco and Bahrain receive defensible implementation/stop decisions and all implemented heads are validated.
