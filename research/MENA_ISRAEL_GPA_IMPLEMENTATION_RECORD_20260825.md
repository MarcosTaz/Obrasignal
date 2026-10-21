# ObraSignal — MENA Israel GPA implementation record

RESEARCHED_AT: 2026-08-25
LAST_LIVE_VALIDATED_AT: 2026-08-25
SOURCE_LAST_OBSERVED_AT: 2026-08-25
CELL: MENA
COUNTRY: Israel
ISO2: IL
ISO3: ISR

## Scope

LIMITED HIGH-VALUE SLICE: recent Public Tender / Central Tender notices discoverable from the official Government Procurement Administration `mr.gov.il` public search, enriched through official public notice detail pages and conservatively filtered for construction/public-works relevance.

This is not every Israeli public buyer, complete history, awards/exemptions, or full national lifecycle coverage.

## Stable source identity

Registry candidate key: `IL_GPA`
Stable source id: `il_gpa_mr_public_procurement`
Publisher/system: Government Procurement Administration / mr.gov.il
Primary official source: `https://mr.gov.il/ilgstorefront/en/search/?s=TENDER`
Detail identity route: `https://mr.gov.il/ilgstorefront/en/p/{serial}`

Identity is publisher-native numeric `Serial`; title, URL hash and translation are not identity. `Process` is retained as secondary publisher metadata.

## Observed facts

On 2026-08-25 the official tender search exposed approximately 21,955 tender results and records with type, Publisher, Serial, Process, Published, Updated and Deadline. Public detail pages were accessible without login.

The portal also exposes RFI, Intent to Contract and Exempt semantics. v0 deliberately does not collapse those into `TENDER`; they remain evidence for a later explicit canonical semantic decision.

## Technical route

OFFICIAL SEARCH HTML -> publisher detail links -> bounded public detail GET -> field parse -> fail-closed construction filter -> publisher-native Serial identity -> canonical TENDER normalization -> canonical Signal store test.

The implementation limits detail fetches to 25 per run, bounds response size/timeouts, rejects identity mismatch and malformed chronology, and treats transport/source-contract failures as errors rather than zero opportunities.

## Construction filter / adversarial corrections

Initial live parsing was technically correct but the first classifier was semantically over-inclusive because broad/hidden `Subjects` taxonomy text could leak into admission. A live sample admitted unrelated gift vouchers, water dispensers and paper products. That design was rejected.

A second title-only classifier still admitted consulting notices because Hebrew terms for establishment, sewer/water and `מבנה` can occur in non-physical organizational contexts. Those ambiguous terms were removed.

Final v0 admission uses only strong physical-works evidence in the publisher title. `Subjects` remain preserved as metadata but cannot admit a record. Precision is intentionally preferred over recall.

Regression cases explicitly exclude:
- `4000621188` gift vouchers even when broad construction-like subject metadata appears;
- `4000619436` consulting/support for establishment of water/sewer corporations;
- `4000620878` salary/organizational consulting for water/sewer corporations;
- English substring traps such as `broadband` / `roadmap`.

Final exact-head live validation on connector head `f37fa47ed877995b35fa244e7fba914a86716a70` fetched 20 official detail notices and admitted exactly one construction tender in that bounded window: `4000621193`, the public tender for renovation of two hospital departments in Nahariya. Independent official-source verification confirmed that tender's physical renovation semantics.

## Access / rights

ACCESS: public unauthenticated HTML search + public detail pages.
SOURCE STATE: AVAILABLE at last observation.
MACHINE ACCESS: VERIFIED for the bounded public route.
RIGHTS: YELLOW / LEGAL REVIEW REQUIRED. Public readability is not commercial redistribution authorization.

No authentication, CAPTCHA, private API, signed session, anti-bot bypass or credentials are used.

## Implementation state

RESEARCHED: YES
TECHNICALLY_PROVEN: YES
IMPLEMENTED: YES
TESTED: YES
LIVE_VALIDATED: YES
PRODUCTION_PATH_VALIDATED: NO
GATED: YES
RUNTIME_ENABLED: NO
PRODUCTION: NO

## Test basis

Exact connector head `f37fa47ed877995b35fa244e7fba914a86716a70`:
- Israel GPA Live Gate: SUCCESS.
- ObraSignal Quality: SUCCESS.
- Live result: 20 notices -> 1 construction signal (`4000621193`) after adversarial false-positive corrections.
- Canonical Signal-store idempotency is covered by repository tests.

This evidence-file update changes the PR head and therefore must itself receive a final exact-head CI pass before merge/consolidation; code semantics above refer to the validated connector commit.

## Conflict record

CONFLICT — PR #173 research-only TECH LAB finding vs later implementation-first proof

previous finding: Israel was TECH LAB; no supported machine route or explicit commercial reuse licence was verified.

new finding: the public official search/detail route is technically implementable without authentication or bypass, while commercial reuse remains unresolved.

likely explanation: PR #173 correctly applied production rights gating but the later MENA rule explicitly separates technical implementation from production enablement.

recommended canonical resolution: preserve #173 as historical evidence; classify this bounded source as IMPLEMENTED / TESTED / LIVE_VALIDATED / GATED, rights YELLOW, runtime disabled.

## Duplication / reuse check

No competing Israel GPA connector/source record was found before branch creation. Qatar/Ashghal was evaluated and rejected as a shared family because Israel uses search discovery + per-notice detail enrichment and different identity/update/filter semantics. HTML similarity is not a family contract.

No regional runtime or `MENAConnectorBase` was created.

## Canonical Integration Manifest

CELL: MENA
COUNTRIES: Israel (IL / ISR)
SOURCE RECORDS ADDED: cell-scoped candidate `IL_GPA` / `il_gpa_mr_public_procurement`
SOURCE RECORDS UPDATED: none
SHARED FAMILIES: none
CODE PRs: PR #187, branch `feature/il-gpa-construction-tenders-v0`
RESEARCH PRs: related historical evidence PR #173
CANONICAL FILES TO UPDATE LATER: `source_registry.py` via controlled International Consolidation Pass; do not duplicate if another cell lands `IL_GPA` first
CONFLICTS: PR #173 TECH LAB/no-build conclusion vs later technical implementation proof; preserved above
DEPENDENCIES: none; branch based on real main SHA `52e011083545a2e69526cd8e0a294cfb61682884`
BLOCKERS: commercial reuse rights not GREEN; runtime intentionally absent
MERGE RISKS: low for new connector/tests/evidence; canonical registry intentionally deferred to reduce cross-cell conflicts
SAFE INTEGRATION NOTES: search for `IL_GPA` / `il_gpa_mr_public_procurement`; append/enrich one canonical source record with country ISR, official source, machine access VERIFIED while live evidence remains current, rights YELLOW, status planned, adapter `IsraelGPAConnector`, signal type TENDER. Never replace the whole registry.

## Required zero-* checks

ZERO-LOSS: PASS — code, evidence, classifier corrections, statuses and provenance survive independently.
ZERO-DUPLICATION: PASS at last cell check; recheck during global consolidation.
ZERO-SILENT-CONFLICT: PASS — #173 difference is explicit.
ZERO-RUNTIME-FORK: PASS — no regional runtime.

## Stop status

SECOND IMPLEMENTATION WIN achieved technically. This does not complete the MENA cell; Oman third-win work and remaining-market decisions continue under the continuation override.
