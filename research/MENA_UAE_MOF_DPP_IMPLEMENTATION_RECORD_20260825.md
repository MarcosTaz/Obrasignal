# ObraSignal — MENA UAE federal MoF DPP implementation record

RESEARCHED_AT: 2026-08-25
LAST_LIVE_VALIDATED_AT: pending exact-head CI
SOURCE_LAST_OBSERVED_AT: 2026-08-25
CELL: MENA
COUNTRY: United Arab Emirates
ISO2: AE
ISO3: ARE

## Scope

LIMITED HIGH-VALUE SLICE: current open federal-entity opportunities publicly listed by the UAE Ministry of Finance under Current Business Opportunities, construction/public-works rows only.

This is federal-only. It is not Dubai procurement, Abu Dhabi procurement, every UAE public buyer, or full award/contract lifecycle coverage.

## Stable source identity

Registry candidate key: `AE_MOF_DPP`
Stable source id: `ae_mof_dpp_public_business_opportunities`
Publisher/system: UAE Ministry of Finance / Digital Procurement Platform
Primary official source: `https://mof.gov.ae/en/public-finance/government-procurement/current-business-opportunities/`

Stable signal identity is publisher RFQ Number. Opportunity links at `procurement.gov.ae` are preserved when present but are not used as identity.

## Observed facts

On 2026-08-25 the official Ministry of Finance page stated that it provides an overview of actual federal entities tenders and exposed RFQ Number, Entity Name, Title, Open Date, Close Date and a procurement-platform link. Current examples included RFQ `12051`, Ministry of Education, `DESIGN AND BUILD CONTRACT FOR SPORTS FIELDS AND THEIR COMPONENTS`, opened 18/08/2026 and closing 08/09/2026.

The same current page included RFQ `12082` for inspection/verification/tagging/valuation of federal infrastructure assets. That record is intentionally not admitted merely because its title says infrastructure: it is an asset-verification service, demonstrating why the construction classifier uses strong physical-works phrases rather than generic sector words.

The Ministry describes the Digital Procurement Platform as the federal procurement platform supporting tender announcement, bid submission, tracking and award. Supplier qualification/participation requires registration and UAE PASS, while the Current Business Opportunities overview is publicly readable without login. Foreign suppliers are an explicit supported supplier type in the federal supplier register.

## Technical route

OFFICIAL CURRENT BUSINESS OPPORTUNITIES HTML -> bounded public pagination -> RFQ table parse -> dedupe/convergence detection -> strong physical-works filter -> native RFQ identity -> canonical TENDER normalization -> canonical Signal store test.

Open Date maps to publisher publication/open timestamp; Close Date maps to deadline. Source-updated timestamp remains unknown because the RFQ rows do not expose one.

## Construction filter

Admission uses strong physical-work terms such as design-and-build, construction, civil/building/road/bridge works, renovation, rehabilitation and strong Arabic equivalents. `infrastructure` alone is deliberately insufficient, preventing professional-services/asset-valuation false positives such as RFQ 12082.

## Access / rights

ACCESS: public unauthenticated Ministry of Finance HTML overview.
SOURCE STATE: AVAILABLE at observation time.
MACHINE ACCESS: technically proven only after exact-head live CI.
RIGHTS: YELLOW / LEGAL REVIEW REQUIRED. The Ministry site states all rights reserved; public readability is not treated as commercial redistribution permission.

Bidding/qualified-supplier actions may require UAE PASS and registration, but the implemented route does not access those authenticated functions.

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

CONFLICT — PR #173 UAE limited-slice research vs concrete federal implementation

previous finding: UAE national coverage is fragmented; federal-first was a useful limited-market slice, but no production connector was built.

new finding: the Ministry of Finance public Current Business Opportunities overview exposes sufficient stable, dated RFQ data for a bounded federal technical connector without login. Commercial reuse rights remain unresolved.

recommended canonical resolution: preserve #173 as historical evidence; after green CI classify candidate `AE_MOF_DPP` as IMPLEMENTED / TESTED / LIVE_VALIDATED / GATED, explicitly federal-only and rights YELLOW.

## Duplication / reuse check

Repository/PR search before branch creation found no competing UAE federal DPP implementation. Qatar, Israel and Oman connectors were reviewed conceptually but not reused as a shared family: this source has its own RFQ schema, AM/PM timestamps, pagination/convergence behavior and procurement.gov.ae detail links.

No UAE/MENA runtime silo is introduced.

## Canonical Integration Manifest

CELL: MENA
COUNTRIES: United Arab Emirates (AE / ARE)
SOURCE RECORDS ADDED: cell-scoped candidate `AE_MOF_DPP` / `ae_mof_dpp_public_business_opportunities`
SOURCE RECORDS UPDATED: none
SHARED FAMILIES: none
CODE PRs: implementation PR from `feature/ae-mof-federal-opportunities-v0`
RESEARCH PRs: related historical evidence PR #173
CANONICAL FILES TO UPDATE LATER: `source_registry.py` through controlled International Consolidation Pass; preserve federal-only jurisdiction metadata and do not merge this identity with future Dubai/Abu Dhabi sources
CONFLICTS: #173 limited-slice/no-build research vs later technical implementation proof; explicit above
DEPENDENCIES: none; branch based on real main SHA `52e011083545a2e69526cd8e0a294cfb61682884`
BLOCKERS: commercial reuse rights not GREEN; runtime intentionally absent
MERGE RISKS: low for new code/tests/evidence; canonical registry deferred
SAFE INTEGRATION NOTES: search `AE_MOF_DPP` / `ae_mof_dpp_public_business_opportunities`; append/enrich one federal source record with country ARE, jurisdiction UAE Federal Government, TENDER capability, rights YELLOW, status planned, adapter `UAEMoFDPPConnector`. Dubai/Abu Dhabi remain distinct source identities if later implemented. Never replace the global registry.

## Required zero-* checks

ZERO-LOSS: PASS if record + code PR are retained.
ZERO-DUPLICATION: PASS at branch creation; recheck global consolidation.
ZERO-SILENT-CONFLICT: PASS; prior limited-slice conclusion is explicitly reconciled.
ZERO-RUNTIME-FORK: PASS.

## Stop status

This is a fourth-win candidate. It does not complete the MENA cell; remaining Saudi Arabia, Morocco, Bahrain and Kuwait still require defensible implementation/stop decisions after validation.
