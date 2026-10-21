# ObraSignal — MENA Morocco PMMP implementation record

RESEARCHED_AT: 2026-08-25
LAST_LIVE_VALIDATED_AT: pending exact-head CI
SOURCE_LAST_OBSERVED_AT: 2026-08-25
CELL: MENA
COUNTRY: Morocco
ISO2: MA
ISO3: MAR

## Scope

LIMITED HIGH-VALUE SLICE: current consultations returned by the official Moroccan Public Procurement Portal (PMMP) category `Travaux de construction et d’aménagement`, normalized as canonical `TENDER`.

This does not claim every PMMP works category or complete lifecycle coverage. The portal also publishes forecast programmes, final results, completion reports, awarded purchase orders and awarded contracts; those are future enrichments of the same source identity.

## Stable source identity

Registry candidate key: `MA_PMMP`
Stable source id: `ma_pmmp_public_procurement`
Publisher/system: Trésorerie Générale du Royaume / Portail Marocain des Marchés Publics
Primary official route: `https://www.marchespublics.gov.ma/index.php?AllCons=&EnCours=&domaineActivite=1.15&page=entreprise.EntrepriseAdvancedSearch`

Tender references are not assumed globally unique across all buyers. v0 external identity therefore uses an explicit publisher composite `buyer::reference`, while preserving the native reference separately as `source_reference`; no title hash or URL identity is used.

## Observed facts

On 2026-08-25 the official portal was publicly readable without authentication and the construction/aménagement category returned 519 consultations over 52 pages. Current rows included publication date, native reference, object, public buyer, execution location and bid deadline. Examples published 22 August 2026 included references `63/2026`, `62/2026`, `61/2026` and `60/2026` for construction of public facilities in Sidi Ifni, with October 2026 deadlines.

The portal home currently exposes large first-class Travaux categories including roads, hydraulic works, sanitation/water/networks, engineering structures, electricity, construction/aménagement, installations, earthworks, foundations and finishing. The advanced public navigation also exposes forecast-program announcements, final results, completion reports and awarded-market lists.

## Technical route

OFFICIAL PMMP CONSTRUCTION-CATEGORY HTML -> table parse -> publisher next-page link discovery -> bounded pagination -> buyer+native-reference identity -> publication/deadline normalization -> canonical TENDER -> canonical Signal-store test.

Because this slice is already publisher-classified as `Travaux de construction et d’aménagement`, v0 does not apply a second keyword classifier that could contradict the official category. Source/category semantics are retained in taxonomy metadata.

## Access / rights

ACCESS: public unauthenticated portal search/listing.
SOURCE STATE: AVAILABLE at observation time.
MACHINE ACCESS: technically proven only after exact-head live CI.
RIGHTS: YELLOW / LEGAL REVIEW REQUIRED. Portal copyright/terms require legal review before commercial redistribution; public access alone is not authorization.

No authentication or electronic-submission functions are used.

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

CONFLICT — PR #173 Morocco HOLD vs concrete PMMP public construction route

previous finding: Morocco was held after the broad MENA audit; no connector was implemented.

new finding: the official PMMP exposes a public, category-filtered current consultation list with hundreds of construction/aménagement records, native references, buyers, dates and deadlines, sufficient for a bounded technical connector. Commercial reuse remains unresolved.

recommended canonical resolution: preserve #173 as historical evidence; after green CI classify `MA_PMMP` as IMPLEMENTED / TESTED / LIVE_VALIDATED / GATED for this construction TENDER slice, with forecast programmes/awards as future source enrichments.

## Duplication / family check

Repository/PR search found no competing Morocco PMMP connector before branch creation. No MENA shared family is used; PMMP category/search/pagination and identity semantics are distinct.

## Canonical Integration Manifest

CELL: MENA
COUNTRIES: Morocco (MA / MAR)
SOURCE RECORDS ADDED: cell-scoped candidate `MA_PMMP` / `ma_pmmp_public_procurement`
SOURCE RECORDS UPDATED: none
SHARED FAMILIES: none
CODE PRs: implementation PR from `feature/ma-pmmp-construction-v0`
RESEARCH PRs: historical MENA evidence PR #173
CANONICAL FILES TO UPDATE LATER: `source_registry.py` through controlled International Consolidation Pass; later PMMP PROCUREMENT_PLAN/AWARD/CONTRACT capabilities must enrich the same source record
CONFLICTS: #173 HOLD vs later concrete public technical route; explicit above
DEPENDENCIES: none; branch based on real main SHA `52e011083545a2e69526cd8e0a294cfb61682884`
BLOCKERS: commercial reuse rights not GREEN; runtime disabled
MERGE RISKS: low for new files; canonical registry deferred
SAFE INTEGRATION NOTES: search `MA_PMMP` / `ma_pmmp_public_procurement`; append/enrich one canonical source with country MAR, TENDER capability, rights YELLOW, status planned, adapter `MoroccoPMMPConnector`. Preserve the buyer+reference identity rule unless a stable publisher consultation ID is later proven and migrated deliberately.

## Required zero-* checks

ZERO-LOSS: PASS if record + code PR retained.
ZERO-DUPLICATION: PASS at branch creation; recheck consolidation.
ZERO-SILENT-CONFLICT: PASS.
ZERO-RUNTIME-FORK: PASS.

## Stop status

This is a sixth-win candidate. MENA is not complete until Saudi Arabia and Bahrain receive final defensible implementation/stop decisions and all candidate heads are validated.
