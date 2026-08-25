# ObraSignal — MENA Oman Esnad upcoming-tender implementation record

RESEARCHED_AT: 2026-08-25
LAST_LIVE_VALIDATED_AT: pending exact-head CI
SOURCE_LAST_OBSERVED_AT: 2026-08-25
CELL: MENA
COUNTRY: Oman
ISO2: OM
ISO3: OMN

## Scope

LIMITED HIGH-VALUE SLICE: official public Esnad/Tender Board `Upcoming Tender` view, construction/public-works rows only. These are pre-publication early signals and are normalized to canonical `PROCUREMENT_PLAN`.

This is not every internal Project/Tender Preparation Plan field, not full national tender lifecycle coverage, and not a claim that every internal plan is publicly visible.

## Stable source identity

Registry candidate key: `OM_ESNAD`
Stable source id: `om_esnad_public_procurement`
Publisher/system: Projects, Tenders and Local Content Authority / Esnad eTendering public dashboard
Primary official source: `https://etendering.tenderboard.gov.om/product/publicDash?viewFlag=UpcomingTenders`

The stable publisher identity for each upcoming row is the numeric internal ID displayed in brackets before the tender number. The tender number is retained as `source_reference`.

## Observed facts

On 2026-08-25 the official public dashboard exposed an `Upcoming Tender` table with S.No., Tender No, Tender Title, Entity, Category and Action. Current rows included numeric IDs such as `96782`, `96772`, `95841` and `95834`. Construction-relevant examples included exterior parking maintenance and building-maintenance rows under construction/maintenance procurement categories.

The authority previously announced that a Project/Tender Preparation Plan becomes a mandatory prerequisite before tender publication effective 15 March 2026. This strengthens the interpretation of the public `Upcoming Tender` surface as a genuine pre-publication procurement signal, but this implementation does not equate the public table with the complete internal plan object.

The same public system also exposes floated/open/awarded/cancelled tender surfaces and detailed Notice Inviting Tender pages. Those lifecycle stages are intentionally not duplicated in v0; they are future enrichment candidates of this same stable source, not separate country sources.

## Technical route

OFFICIAL UPCOMING TENDER HTML -> table parse -> internal numeric identity + tender number -> conservative construction filter -> canonical PROCUREMENT_PLAN normalization -> canonical Signal store test.

No publisher date/deadline exists in the public upcoming table, so the connector deliberately leaves those fields unknown rather than inventing timestamps.

## Construction filter

Admission uses explicit construction/maintenance procurement categories plus strong English/Arabic physical-works title terms. Generic supply/installation does not qualify by itself. Precision is preferred over recall.

## Access / rights

ACCESS: public unauthenticated HTML.
SOURCE STATE: AVAILABLE at observation time.
MACHINE ACCESS: technically proven only after exact-head live CI.
RIGHTS: YELLOW / LEGAL REVIEW REQUIRED. The dashboard labels part of its reporting as open data, but that label is not treated as sufficient proof of commercial SaaS redistribution rights for the granular upcoming-tender table.

No login, PKI, CAPTCHA, private endpoint, session bypass or credentials are used.

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

CONFLICT — PR #173 Oman TECH LAB vs new implementable early-signal route

previous finding: Oman public dashboards were visible, but machine extraction and reuse rights were not proven; Oman remained TECH LAB.

new finding: the public `Upcoming Tender` table exposes stable numeric identities and structured pre-publication rows suitable for a bounded technical connector. Commercial reuse remains unresolved.

evidence: official Esnad/Tender Board public dashboard observed 2026-08-25; implementation and exact-head CI in this PR.

likely explanation: prior research correctly separated public readability from production rights but did not yet exploit the public Upcoming Tender surface as a bounded early-signal slice.

recommended canonical resolution: preserve PR #173 as historical evidence; after green CI classify `OM_ESNAD` as IMPLEMENTED / TESTED / LIVE_VALIDATED / GATED for PROCUREMENT_PLAN capability, while leaving legal reuse YELLOW and runtime disabled.

## Duplication / family check

Repository/PR search before implementation found no competing Oman Tender Board connector. The prior Oman/Bahrain shared-family idea remains unproven; this connector is not generalized into a GCC/MENA family because transport, identity, pagination and rights equivalence have not been demonstrated.

Qatar/Ashghal and Israel/GPA are related MENA work but not dependencies.

## Canonical Integration Manifest

CELL: MENA
COUNTRIES: Oman (OM / OMN)
SOURCE RECORDS ADDED: cell-scoped candidate `OM_ESNAD` / `om_esnad_public_procurement`
SOURCE RECORDS UPDATED: none
SHARED FAMILIES: none
CODE PRs: implementation PR from `feature/om-tenderboard-public-tenders-v0`
RESEARCH PRs: related historical evidence PR #173
CANONICAL FILES TO UPDATE LATER: `source_registry.py` through controlled International Consolidation Pass; enrich one `OM_ESNAD` source with PROCUREMENT_PLAN and any later proven lifecycle capabilities rather than create multiple Esnad source identities
CONFLICTS: PR #173 TECH LAB finding vs later public Upcoming Tender technical proof; recorded above
DEPENDENCIES: none; branch based on real main SHA `52e011083545a2e69526cd8e0a294cfb61682884`
BLOCKERS: commercial reuse rights not GREEN; runtime intentionally absent
MERGE RISKS: low for new code/tests/evidence; canonical source registry intentionally deferred
SAFE INTEGRATION NOTES: search for `OM_ESNAD` and `om_esnad_public_procurement` at consolidation; merge/enrich one canonical source record, never replace the global registry. Keep signal type `PROCUREMENT_PLAN`; do not create an Oman-specific signal type.

## Required zero-* checks

ZERO-LOSS: PASS if this record + code PR are retained.
ZERO-DUPLICATION: PASS at branch creation; recheck at global consolidation.
ZERO-SILENT-CONFLICT: PASS; PR #173 difference explicitly preserved.
ZERO-RUNTIME-FORK: PASS; no Oman/MENA runtime introduced.

## Stop status

This is a third-win candidate and does not complete the MENA cell by itself. Remaining markets still require defensible decisions under the continuation override.
