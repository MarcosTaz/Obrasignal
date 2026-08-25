# ObraSignal — MENA Israel GPA implementation record

RESEARCHED_AT: 2026-08-25
LAST_LIVE_VALIDATED_AT: pending exact-head CI
SOURCE_LAST_OBSERVED_AT: 2026-08-25
CELL: MENA
COUNTRY: Israel
ISO2: IL
ISO3: ISR

## Scope

LIMITED HIGH-VALUE SLICE: recent public/central tender notices discoverable from the official Government Procurement Administration `mr.gov.il` public search, enriched through official public notice detail pages and conservatively filtered for construction/public-works relevance.

This is not a claim of every Israeli public buyer, every historical notice, awards, exemptions, or full national lifecycle coverage.

## Stable source identity

Registry candidate key: `IL_GPA`
Stable source id: `il_gpa_mr_public_procurement`
Publisher/system: Government Procurement Administration / mr.gov.il
Primary official source: `https://mr.gov.il/ilgstorefront/en/search/?s=TENDER`
Detail identity route: `https://mr.gov.il/ilgstorefront/en/p/{serial}`

Identity is the publisher-native numeric `Serial`, not title, URL hash, or translated text. `Process` is retained as secondary publisher reference metadata.

## Observed facts

On 2026-08-25 the official English tender search exposed approximately 21,955 tender results and current records with type, publisher, Serial, Process, Published, Updated and Deadline fields. Public detail pages were accessible without login and exposed the same native identity plus subjects. Current examples observed included Serial `4000617670`, a public tender concerning planning/financing/construction/operation/maintenance of rooftop photovoltaic facilities, and Serial `4000615733`, an architectural-services tender for a hospital project.

The same portal also exposes RFI, Intent to Contract and Exempt semantics. They are preserved as research evidence but are deliberately not mapped into v0 because ObraSignal must not silently collapse distinct procurement semantics into `TENDER`. Future integration may map compatible early-signal types to canonical `MARKET_DIALOGUE` or another approved canonical type only after an explicit semantic decision.

## Technical route

OFFICIAL SEARCH HTML -> publisher detail links -> bounded public detail GET -> field parse -> construction filter -> publisher-native Serial identity -> canonical `TENDER` normalization -> canonical Signal store test.

The implementation limits detail fetches per run, enforces response-size limits and timeout bounds, rejects identity mismatches, rejects malformed dates, and treats transport/source-contract failure as errors rather than zero opportunities.

## Construction filter

Conservative bilingual title/subject terms are used. The source's English `Subjects` field is preferred where useful; Hebrew construction-specific stems cover cases where titles express works more clearly than subject taxonomy. Generic procurement words are not sufficient for admission.

## Access / rights

ACCESS: public unauthenticated HTML search + public detail pages observed.
SOURCE STATE: AVAILABLE at observation time.
MACHINE ACCESS: technically proven only after exact-head live CI.
RIGHTS: YELLOW / LEGAL REVIEW REQUIRED. Public readability is not treated as commercial redistribution authorization.

No authentication, CAPTCHA, private API, signed session, anti-bot bypass or credential route is used.

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

CONFLICT — previous PR #173 finding vs implementation-first continuation

previous finding: Israel was TECH LAB; no supported machine route or explicit commercial reuse licence was verified.

new finding: the public official search/detail route is technically implementable as a bounded limited slice without authentication or bypass. This does not prove commercial reuse rights.

evidence: official mr.gov.il search/detail pages observed 2026-08-25; code and exact-head CI in this implementation PR.

likely explanation: the previous audit correctly applied production gating but treated unresolved rights as a reason not to engineer a technical slice. The later MENA continuation rule explicitly separates implementation proof from production enablement.

recommended canonical resolution: retain PR #173 as historical evidence; classify the source, after green CI, as IMPLEMENTED / TESTED / LIVE_VALIDATED / GATED, with legal reuse unresolved and runtime disabled.

## Duplication / reuse check

No existing Israel GPA connector/source record was found in repository/PR search before branch creation. Qatar/Ashghal was evaluated for reuse but rejected as a shared family: both are public HTML, yet Israel uses search discovery + per-notice detail enrichment and different identity/update/subject semantics. HTML similarity is not a family contract.

No regional runtime or `MENAConnectorBase` was created.

## Canonical Integration Manifest

CELL: MENA
COUNTRIES: Israel (IL / ISR)
SOURCE RECORDS ADDED: cell-scoped candidate `IL_GPA` / `il_gpa_mr_public_procurement`
SOURCE RECORDS UPDATED: none
SHARED FAMILIES: none
CODE PRs: implementation PR opened from `feature/il-gpa-construction-tenders-v0`
RESEARCH PRs: related historical evidence PR #173
CANONICAL FILES TO UPDATE LATER: `source_registry.py` via controlled International Consolidation Pass; do not duplicate if another cell lands `IL_GPA` first
CONFLICTS: PR #173 TECH LAB/no-build conclusion vs later technical implementation proof; preserved above
DEPENDENCIES: none; branch is based on real `main` SHA `52e011083545a2e69526cd8e0a294cfb61682884`
BLOCKERS: commercial reuse rights not GREEN; runtime integration intentionally absent
MERGE RISKS: low for new connector/tests/evidence; canonical registry intentionally deferred to reduce cross-cell conflicts
SAFE INTEGRATION NOTES: merge adapter/tests/evidence first; during consolidation search for `IL_GPA`/`il_gpa_mr_public_procurement`; append/enrich one canonical source record with country ISR, official source, machine access VERIFIED only if live CI remains valid, rights YELLOW, status planned, adapter `IsraelGPAConnector`, signal type TENDER. Never replace the whole global registry.

## Required zero-* checks

ZERO-LOSS: PASS if this record + code PR are preserved; evidence, decision, status and provenance survive independently.
ZERO-DUPLICATION: PASS at branch creation; no competing Israel GPA source implementation found. Recheck at global consolidation time.
ZERO-SILENT-CONFLICT: PASS; PR #173 conflict explicitly recorded.
ZERO-RUNTIME-FORK: PASS; no regional runtime created.

## Stop status

This record is a second-win candidate record, not a declaration that the MENA cell is complete. Remaining markets must continue under the MENA continuation override after this implementation is validated.
