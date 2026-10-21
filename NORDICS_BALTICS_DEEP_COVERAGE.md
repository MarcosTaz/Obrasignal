# Nordics + Baltics deep coverage

Status: country-cell evidence and implementation record, 2026-08-25.

This document does not change the canonical Master Execution Queue. It records
incremental national value above TED/eForms and the implementation decision made
by the autonomous country cell.

## Executive decision

| Market | Classification | National value beyond TED | Technical outcome |
| --- | --- | --- | --- |
| Denmark | BUILD/PREPARED — credential gated | Udbud.dk exposes below-threshold purchasing, expected purchases/plans and searchable national notices through an official API. | No connector built in this cell: system-provider API account is required before source-contract/live validation. |
| Norway | BUILD/PREPARED — credential gated | Doffin covers procurement above the Norwegian national threshold, including notices below EEA/TED thresholds; planning/result forms also exist. | No connector built in this cell: public API shape is technically credible, but official key/reuse onboarding was not closed strongly enough for production-source registration. |
| Sweden | PARTNERSHIP/LICENSE / HOLD | Below-EU-threshold notices are nationally material, but publication is split across registered commercial advertisement databases. | No bespoke connector. A partnership/licensed aggregation route is economically preferable to multi-platform scraping/integration. |
| Finland | BUILD/PREPARED — implemented, credential gated | HILMA AVP adds national works notices and procurement plans below the TED baseline through one official API. | **Implemented in this branch:** `FI_HILMA` connector, Signal normalization, pagination, cursor overlap, runtime wiring and tests. Registry remains planned/CREDENTIAL_REQUIRED until a real AVP key is live-validated. |
| Estonia | NATIONAL ENRICHMENT — already implemented | Official RHR eForms bulk provides country-native works/lifecycle identity beyond the generic TED feed. | Existing `EE_RHR`; live validation and CI evidence pre-date this cell. No duplicate build. |
| Lithuania | NATIONAL ENRICHMENT — already implemented | Official CVP IS snapshot exposes national Works records with publisher-native classification and lifecycle reconciliation. | Existing `LT_VPT`; no duplicate build. |
| Latvia | NATIONAL ENRICHMENT — already implemented | Official IUB daily JSON covers national notices via a CC0 source and stable incremental ingestion. | Existing `LV_IUB`; no duplicate build. |
| Iceland | TED/PORTAL SUFFICIENT FOR CURRENT PHASE / HOLD | Útboðsvefur is the national public-tender portal and can include below-threshold notices, but no sufficiently proven public machine-readable API/open-data route was found. | Small-market rule: no bespoke build until a low-burden official feed/API appears. |

## Finland — implementation record

### Current TED baseline

TED remains the shared European baseline for Finnish above-threshold eForms.
The HILMA implementation is additive and does not replace TED or fork the
canonical Opportunity model.

### Official source

HILMA / hankintailmoitukset.fi AVP read API:

- search endpoint: `POST https://api.hankintailmoitukset.fi/avp/eformnotices/docs/search`;
- authentication: `Ocp-Apim-Subscription-Key`;
- credential: free self-service AVP subscription key;
- commercial use: permitted by the HILMA developer terms reviewed by this cell;
- current production gate: credential/live validation required.

### Added value

Implemented source-native slices:

- `ContractNotices` + `procurementTypeCode=works` -> `TENDER`;
- `PlanNotices` + `procurementTypeCode=works` -> `PROCUREMENT_PLAN`.

Procurement plans are persisted/staged as canonical Signals but are deliberately
excluded from the legacy `tenders` projection.

### Identity

- source publication identity: `noticeId`;
- eForms notice identity: `eFormsId` when present;
- procedure reference: `procedureId`, falling back to `eFormsId`, then `noticeId`.

The connector rejects duplicate publication ids within a bounded scan and uses
an overlap cursor so delayed/index-updated records do not silently disappear.

### Pagination and incremental ingestion

- bounded Azure Search `skip`/`top` pagination;
- separate complete scans for tender and plan signal families;
- stable ascending publication ordering requested;
- 48-hour overlap on the publication watermark;
- cursor is returned only after both scans complete;
- malformed envelopes, duplicate ids, missing ids and page-bound overruns fail closed.

### Construction filter

`procurementTypeCode=works` is the publisher-native admission gate. CPV codes are
preserved for matching/filtering, but keywords are not used as the primary
construction classifier.

### Failure isolation

Runtime composition uses `incremental_runtime_plugin.py`. A HILMA failure:

- records source failure health;
- does not stage/advance the HILMA cursor;
- does not remove TED or other national-source records already fetched.

### Rights and production gate

The connector contains no credential. `HILMA_API_KEY` is read from the runtime
environment. Because this cell did not possess a real AVP key, the source
registry is deliberately:

- `status="planned"`;
- `machine_access="CREDENTIAL_REQUIRED"`.

This prevents a false production-ready claim. Code readiness and live source
readiness are intentionally separate.

### Tests

The PR quality workflow covers:

- Python compile;
- full repository pytest suite;
- Finland works filtering;
- tender/plan signal semantics;
- stable identity mapping;
- pagination;
- cursor overlap;
- duplicate-page fail-closed behavior;
- invalid envelopes;
- missing credentials;
- runtime Signal staging and legacy TENDER projection;
- source-failure isolation;
- registry production gating;
- Expo Doctor, critical mobile wiring and web bundle smoke.

## Denmark

Official Udbud.dk documentation states that system providers can use its API to
create below-threshold purchases and expected purchases and fetch procurement
notices for search. Reproduction for commercial tender intermediaries is
permitted with source attribution. The platform also exposes expected purchases
that are not searchable in TED. This is material national depth.

The cell did not build from an unvalidated account-bound API contract. Reopen as
a connector implementation when a Udbud.dk system-provider account is available
for bounded schema, pagination, identity and live tests.

## Norway

Doffin is mandatory above Norway's national procurement threshold; procurement
above EEA thresholds is additionally published to TED. Therefore the national
feed contains commercially meaningful below-TED procurement.

Technical investigation found a credible current public API shape:
`/public/v2/search` for JSON discovery and `/public/v2/download/{id}` for eForms
XML. Empirical implementations report one-indexed pagination, a 1,000-hit query
cap and duplicate ids across unstable publication-date pages, implying that a
safe connector must use bounded date windows and deduplication rather than a
naive page cursor.

However this cell did not establish the official subscription-key/reuse onboarding
contract strongly enough to register a new production source. The candidate is
therefore prepared, not implemented or live-validated.

## Sweden

The Swedish publication model is structurally fragmented. Public procurement
above direct-award limits is advertised in registered national advertisement
databases; above EU thresholds it is also sent to TED. Official 2025 statistics
record 18,015 advertised procurements across five registered databases, with the
three largest commercial platforms carrying nearly all volume.

The national below-threshold opportunity is real, but building and maintaining
multiple commercial-platform connectors without a license/partnership fails the
100-hour test. Reopen on a lawful aggregated data/API partnership or a public
machine-readable national feed with operational rather than statistical detail.

## Estonia

Repository-first inspection found `estonia_rhr.py`, `estonia_runtime.py` and
country tests already present. The existing connector uses official RHR monthly
eForms XML, admits publisher-native Works records, emits lot-level opportunities
and tracks procedure identity separately from publication identity. Existing
commit evidence records a 2026-08-24 live smoke and green repository/mobile CI.

Decision: **skip with evidence; existing national enrichment is materially deeper
than TED-only coverage.**

## Lithuania

Repository-first inspection found `lithuania_vpt.py`, runtime wiring and tests.
The connector performs a complete bounded CVP IS snapshot because source rows can
change lifecycle state in place, uses publisher-native `procurementType=Works`,
and fails closed on snapshot-integrity errors.

Decision: **skip with evidence; do not duplicate the national connector.**

## Latvia

Repository-first inspection found `latvia_iub.py`, runtime wiring and tests. The
source uses official daily JSON, a reusable bulk adapter, stable procedure/lot
identity handling and CC0 reuse. Existing PR evidence records live validation.
The current implementation intentionally emits the proven TENDER slice only;
planning/result forms are not falsely claimed as implemented Signals.

Decision: **skip with evidence; existing national connector remains the correct
boundary.**

## Iceland

Útboðsvefur is the official common publication platform for Icelandic public,
municipal and utility procurement and may also carry below-threshold notices.
Public tender documents can live in the buyer's tendering system (including
TendSign for the Financial Management Authority). The cell did not find a public,
stable machine-readable official feed/API with sufficiently clear reuse and
identity semantics.

Given the market size and the absence of a proven low-maintenance machine route,
a bespoke portal scraper would fail the small-market and 100-hour tests. TED plus
human portal visibility is retained for the current phase.

## Final cell classification

- **New implementation:** Finland HILMA national works + procurement-plan slice.
- **Existing national implementations confirmed:** Estonia RHR, Latvia IUB,
  Lithuania VPT.
- **Prepared / credential-gated candidates:** Denmark Udbud.dk, Norway Doffin.
- **Partnership/HOLD:** Sweden.
- **Current-phase HOLD under small-market rule:** Iceland.
- **No Nordic abstraction created:** the publisher/transport contracts are not
  sufficiently homogeneous to justify abstraction theatre.
- **Master Queue:** unchanged.
- **Merge/production:** not performed by this cell.
