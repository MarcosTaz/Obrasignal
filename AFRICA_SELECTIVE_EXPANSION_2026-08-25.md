# ObraSignal — Africa Selective Expansion

**Decision date:** 2026-08-25  
**Cell:** AFRICA SELECTIVE EXPANSION  
**Policy:** maximize commercially useful public-works intelligence per engineering and maintenance hour.  
**Repository rule:** this document does not alter `CURRENT_ITEM_ID`, reorder the Master Queue, promote any source to production, or merge code.

## Executive decision

This cell reviewed the requested queue without restarting research already closed by the 2026-08-24 portfolio rebase.

| Country | Final classification | Engineering decision |
|---|---|---|
| South Africa | SHARED COVERAGE | Keep existing National Treasury eTenders implementation through the shared OCDS family; no bespoke expansion now. |
| Kenya | HOLD | Strong central/national-plus-county publication, but commercial-reuse licensing remains unresolved at the open-data publisher layer. |
| Uganda | TECH LAB | e-GP 2.0 materially improves lifecycle value; retain for reusable lifecycle learning until current machine route/reuse and paid demand are proven. |
| Zambia | TECH LAB | Strong OCDS/e-GP technical and legal evidence; retain as shared-family candidate, not a dedicated commercial build. |
| Ghana | REMOVE CURRENT PHASE | Strong human-facing GHANEPS lifecycle, but no proven official machine feed/API plus commercial-reuse contract sufficient to beat the 100-hour test. |
| Namibia | HOLD | Useful official lifecycle exists, but document/entity fragmentation plus small-market economics make new integration irrational today. |
| Tanzania | TECH LAB | Excellent NeST/OCDS technical case and lawful reuse; commercial ARPU/WTP remains the binding blocker. |
| Botswana | REMOVE CURRENT PHASE | Current public procurement discovery exists, but the national e-procurement platform is still a 2027 development target and small-market economics do not justify bespoke work now. |

**New bespoke connectors authorized by this cell: 0.**  
**New production claims: 0.**  
**Master Queue changes: 0.**

## Repository state reused

South Africa is not greenfield. `main` already contains `south_africa_etenders.py`, `test_south_africa_etenders.py` and `test_za_runtime_wiring.py`. The source registry records `ZA_ETENDERS` as a ready, machine-verified, GREEN source using the shared `OCDSAPIConnector`, while the strategic portfolio records South Africa as SHARED rather than a country-specific BUILD.

PR #103 previously added and live-validated the South Africa connector against the official National Treasury OCDS Release API. It intentionally implements **TENDER only** for ObraSignal even though upstream OCDS data contains richer lifecycle structures. Its explicit coverage caveat must be preserved: the National Treasury open-data publication is not guaranteed to contain every South African public procurement process.

## 1. South Africa

### Executive decision

**CLASSIFICATION: SHARED COVERAGE — retain existing implementation; no new bespoke connector.**

### Evidence

- National Treasury eTenders exposes an official public OCDS Release API at `https://ocds-api.etenders.gov.za/api/OCDSReleases` and bulk/open-data publication.
- The official publication policy covers planning, tendering, awards and contracts, provides machine-readable downloads/API, and explicitly warns that data shared with National Treasury is not a complete record of all procurement. Municipalities and state-owned entities can therefore create material coverage gaps.
- Open Contracting's registry shows substantial historical lifecycle data, including planning, tenders, awards and contracts, but also quality/completeness limitations.
- eTenders and National Treasury publish procurement plans, providing genuine early-signal value.
- CIDB classification/prescripts are highly relevant to construction eligibility and filtering.

### Coverage and product boundary

- **Machine source coverage:** material national Treasury dataset, not defensible as complete national procurement coverage.
- **Implemented ObraSignal signal:** TENDER only.
- **Upstream lifecycle:** planning + tender + award + contract structures exist and may justify future shared-family enrichment, but are not declared implemented now.
- **Construction filtering:** strong via works/category fields plus CIDB context; preserve source-native classifications where present.
- **Identity:** OCDS OCID plus tender identifiers are stable enough for shared-family normalization.
- **Auth:** no auth for public OCDS API.
- **Rights:** commercially reusable open-data terms are published. Source-level metadata should be preserved because the API/package and portal pages may surface different compatible licence labels.

### Economics

South Africa has the strongest commercial case in this queue, but the marginal engineering decision is not “build South Africa”: the build already exists. The rational next step is to exploit the shared OCDS family and only add high-value entities/provinces when paid demand proves a gap that the shared source cannot close. Attempting to cover all municipal fragmentation would fail the 500-hour reality test.

### Status

- **IMPLEMENTED:** YES — existing `ZA_ETENDERS` connector in `main`.
- **TESTED:** YES — existing source and runtime tests.
- **LIVE VALIDATED:** YES — historical proof in merged PR #103; this cell did not rerun the production connector from a local checkout because the shell runtime could not resolve GitHub DNS.
- **NEW CODE IN THIS CELL:** NO.

## 2. Kenya

### Executive decision

**CLASSIFICATION: HOLD — reopen gate not satisfied.**

### Evidence

- PPRA/PPIP publishes OCDS covering national and county buyers and is updated daily through 2026.
- PPRA describes PPIP as the mandatory publication/reporting platform for public entities and links it to e-GP integration.
- The open-data publisher currently exposes structured data but does not publish a licence or publication policy in the Open Contracting registry.
- The public portal has broad procuring-entity and contract visibility, so the blocker is not absence of procurement data.

### Decision logic

Kenya remains commercially interesting and technically much better than a portal-only market. However, the canonical reopen condition requires both commercial reuse to become GREEN and machine data completeness to be close enough to the human portal. The first condition is still not proven. No scraping/login bypass or rights assumption is acceptable.

### Status

- **EARLY SIGNAL DEPTH:** procurement publication is broad; plan depth requires further proof before promotion.
- **TENDER COVERAGE:** strong, central + county-oriented PPIP.
- **AWARD/CONTRACT COVERAGE:** material publication exists.
- **AUTH:** public discovery; no bypass required for current evidence.
- **RIGHTS:** LEGAL REVIEW REQUIRED / not GREEN at publisher registry level.
- **IMPLEMENTED:** NO.
- **TESTED:** N/A — no code authorized.
- **LIVE VALIDATED:** public source paths verified; production-path ingestion not tested.

## 3. Uganda

### Executive decision

**CLASSIFICATION: TECH LAB — retain, do not commercial-promote yet.**

### Evidence

- PPDA announced e-GP 2.0 national rollout from 1 July 2026, covering procurement planning, e-bidding, contract management, audit trails, reporting and integration across procuring entities including local government.
- Uganda's older PPDA/Open Contracting dataset is licensed ODC-By and covers many government entities, but its published time range and completeness do not yet prove that the new e-GP 2.0 live lifecycle is exposed through an equally current, stable machine feed.
- Public e-GP pages expose structured procurement references, bid openings and amounts.

### Decision logic

Uganda has unusually valuable lifecycle semantics for a smaller market: plans -> bid invitations -> evaluated-bid notices -> contract award/management. That is worth retaining for reusable architecture learning. It does not yet justify country-specific commercial engineering because the current machine route aligned with e-GP 2.0, its reuse contract, and paid regional traction are not all proven simultaneously.

### Status

- **EARLY SIGNAL DEPTH:** HIGH institutionally; machine-feed currency still unproven.
- **TENDER/AWARD/CONTRACT:** strong lifecycle potential.
- **CONSTRUCTION FILTER:** source classification quality requires live-feed verification.
- **AUTH/RIGHTS:** older open dataset ODC-By; current e-GP 2.0 machine-reuse contract still must be verified before product promotion.
- **IMPLEMENTED:** NO.
- **TESTED:** N/A.
- **LIVE VALIDATED:** public portal/source evidence only, not production connector.

## 4. Zambia

### Executive decision

**CLASSIFICATION: TECH LAB — strongest future shared-OCDS candidate after South Africa; no dedicated build.**

### Evidence

- ZPPA publishes OCDS with current 2026 retrievals and CC BY 4.0 licensing.
- Zambia e-GP exposes hundreds of annual procurement plans, including Road Development Agency, ZESCO, councils, water/sewer entities and other infrastructure buyers.
- Public tender search exposes tender identity, procurement type/CPC, UNSPSC, estimated value and dates.
- The system lists a broad procuring-entity universe and exposes award status/lifecycle information.

### Decision logic

The technical/legal case is good enough for a shared-family experiment, but the portfolio gate is economic: no evidence gathered in this bounded audit proves enough paying demand to justify dedicated support ahead of current priority markets. Therefore Zambia stays TECH LAB rather than being promoted through technical enthusiasm alone.

### Status

- **EARLY SIGNAL DEPTH:** HIGH — annual procurement plans.
- **TENDER COVERAGE:** broad official e-GP.
- **AWARD/CONTRACT:** lifecycle/status evidence exists; exact machine completeness needs connector-level proof.
- **CONSTRUCTION FILTER:** good potential via procurement type/CPC/UNSPSC and infrastructure buyers.
- **AUTH/RIGHTS:** public OCDS; CC BY 4.0.
- **SHARED/BESPOKE:** potential shared OCDS family; bespoke rejected.
- **IMPLEMENTED:** NO.
- **TESTED:** N/A.
- **LIVE VALIDATED:** public paths/data publication verified; no production connector.

## First-four portfolio checkpoint

- **MARKETS REVIEWED:** 4
- **MARKETS RETAINED:** 4 (1 SHARED, 1 HOLD, 2 TECH LAB)
- **BUILD NOW:** 0
- **LIMITED SLICE:** 0 new; South Africa already has an existing limited/qualified shared national dataset rather than full national completeness.
- **HOLD:** 1 — Kenya
- **REMOVE:** 0
- **SHARED FAMILIES:** 1 existing material family — OCDS API/bulk
- **BESPOKE CONNECTORS:** 0 new
- **MARKETS PER CONNECTOR FAMILY:** South Africa already on shared OCDS; Zambia is a credible future shared-family candidate; Uganda remains lifecycle-family research until its current machine route is proven.
- **ENGINEERING HOURS AVOIDED:** no precise project-hours model exists, so no fake exact number is asserted. Under the cell's own 100-hour bespoke-connector test, declining three unjustified bespoke builds avoids at least **300 hours of counterfactual bespoke-build exposure**; this is a decision-test inference, not measured saved labor.
- **EXPECTED MAINTENANCE ADDED:** 0 new connector maintenance from this cell.
- **COMMERCIAL POTENTIAL RETAINED:** South Africa remains commercially active through SHARED coverage; Kenya optionality is retained through HOLD; Uganda/Zambia retain technical option value without committing support cost. No new percentage is invented.

## 5. Ghana

### Executive decision

**CLASSIFICATION: REMOVE CURRENT PHASE — reason refined, not reversed.**

### Evidence

- GHANEPS currently exposes advanced public tender search, annual procurement plans, UNSPSC-oriented classification, procurement methods, estimated values and statuses.
- Current public results include construction works and EOIs.
- GHANEPS publishes awarded contracts with procuring entity, supplier, award date, amount and lot information.
- PPA has required broad government use of GHANEPS and procurement-plan submission.

### Decision logic

Ghana should not be described as a weak digital-procurement market. Its human-facing lifecycle is strong. The binding failure is machine economics: this audit did not prove an official supported API/feed/export contract plus explicit commercial-reuse terms. Building an HTML-specific connector would create brittle maintenance and fail the 100-hour test relative to stronger markets. Reopen if PPA/GHANEPS publishes a supported machine route with commercial reuse, or if a paying customer/partner justifies the burden.

### Status

- **EARLY SIGNAL DEPTH:** HIGH on human portal via annual procurement plans.
- **TENDER/AWARD:** HIGH human-facing visibility.
- **CONTRACT:** awarded-contract data present.
- **CONSTRUCTION FILTER:** good via procurement type + UNSPSC.
- **AUTH:** public search available; supplier/login flows must not be bypassed.
- **RIGHTS:** commercial machine reuse not proven.
- **IMPLEMENTED:** NO.

## 6. Namibia

### Executive decision

**CLASSIFICATION: HOLD — existing vNext override remains defensible.**

### Evidence

- Namibia's official eProcurement ecosystem publishes bid adverts, awards, procurement plans and related procurement documentation.
- Individual ministries/agencies also publish their own annual procurement plans, bids and awards, confirming lifecycle value but also source fragmentation.
- Much of the useful material remains document-centric rather than a proven stable national machine API.

### Decision logic

The blocker is not absence of procurement digitalization. It is the combination of small-market economics, document/entity fragmentation, unproven API/reuse and ongoing maintenance burden. Reopen when a stable reusable machine route or shared adapter reduces marginal cost dramatically, or when concrete customer demand pays for the gap.

### Status

- **EARLY SIGNAL DEPTH:** GOOD via procurement plans.
- **TENDER/AWARD:** official publication exists.
- **CONTRACT:** mixed/document dependent.
- **FRAGMENTATION:** MEDIUM-HIGH.
- **AUTH/RIGHTS:** public documents; machine commercial-reuse route unproven.
- **IMPLEMENTED:** NO.

## 7. Tanzania

### Executive decision

**CLASSIFICATION: TECH LAB — technical winner, commercial gate still closed.**

### Evidence

- NeST supports annual procurement planning, prequalification, tendering, bid opening/evaluation, award and contract management.
- The system covers a large universe of procuring entities, including lower-level entities.
- The official NeST Data Portal documents OCDS REST release/record endpoints and incremental patterns.
- Open Contracting lists PPRA data under CC BY-SA 4.0 with daily publication and broad lifecycle scope, while noting data-quality issues.

### Decision logic

Tanzania is one of the best technical family candidates in this queue and appears legally reusable. The current portfolio classification is still correct because its blocker is commercial ARPU/WTP, not technical access. A dedicated connector would therefore violate the opportunity-cost rule. Reopen for commercial promotion when regional paid demand exists or when inclusion in a shared OCDS family becomes effectively near-zero marginal cost and live production data quality is verified.

### Status

- **EARLY SIGNAL DEPTH:** VERY HIGH — procurement plans/prequalification.
- **TENDER/AWARD/CONTRACT:** broad lifecycle semantics.
- **IDENTITY/INCREMENTAL:** OCDS and documented REST/cursor/since patterns are promising.
- **AUTH/RIGHTS:** public data; CC BY-SA 4.0 at publisher registry level.
- **IMPLEMENTED:** NO.
- **LIVE VALIDATED:** public documentation/current portal checked; no production connector smoke performed.

## 8. Botswana

### Executive decision

**CLASSIFICATION: REMOVE CURRENT PHASE — SMALL MARKET RULE fails today.**

### Evidence

- IPMS provides public annual procurement-plan search and tender discovery with contractor discipline/code/grade dimensions.
- Botswana's government reported in March 2026 that a national e-procurement system is being developed for 2027 to centralize procurement stages and awards, implicitly confirming that current infrastructure is not yet the desired unified national platform.

### Decision logic

Botswana does have useful public procurement information, so the reason for removal should not be “nothing exists.” The problem is timing and economics: small addressable market, no proven open supported machine API/rights, and a new national platform expected in 2027 that could obsolete a bespoke connector built now. Reassess after the 2027 platform launches and exposes a stable machine route with lawful reuse.

### Status

- **EARLY SIGNAL DEPTH:** procurement-plan visibility exists.
- **TENDER:** public discovery exists.
- **AWARD/CONTRACT:** current unified machine lifecycle not proven.
- **CONSTRUCTION FILTER:** contractor discipline/code/grade context is useful.
- **AUTH/RIGHTS:** public search, but machine commercial-reuse route unproven.
- **IMPLEMENTED:** NO.

## Cross-market portfolio view

| Country | Public-works value | Data | Early signal | Award/contract | Reuse | Burden | Commercial | Final decision |
|---|---|---|---|---|---|---|---|---|
| South Africa | Very high | High but incomplete | High | Upstream strong; ObraSignal currently TENDER-only | Existing OCDS family | Low marginal / high if municipal expansion | High | SHARED |
| Kenya | High | High | Medium-High | Strong portal publication | OCDS technically reusable | Low-Medium technical; legal gate | High potential | HOLD |
| Uganda | Medium-High | Improving rapidly | High | High lifecycle potential | Possible lifecycle/OCDS family | Medium | Unproven paid traction | TECH LAB |
| Zambia | Medium | High | High | Good lifecycle potential | Strong OCDS candidate | Low-Medium | Unproven paid traction | TECH LAB |
| Ghana | Medium-High | Strong human portal | High | Strong human portal | No proven machine family contract | Medium-High | Medium | REMOVE |
| Namibia | Low-Medium | Useful but document-centric | Good | Mixed/fragmented | Unproven | Medium-High relative to size | Low-Medium | HOLD |
| Tanzania | Medium-High | Very high technically | Very high | Strong lifecycle | Strong OCDS candidate | Low-Medium shared / poor bespoke economics | Current ARPU/WTP blocker | TECH LAB |
| Botswana | Low-Medium | Partial/current transition | Medium | Not unified enough | Future platform unknown | High relative to size | Low-Medium | REMOVE |

## Shared-family conclusion

No `AfricaProcurementAdapter` should be created. The only defensible cross-country technical family here is standards/transport based:

- existing `OCDSAPIConnector` / OCDS bulk patterns for South Africa and potentially Zambia/Tanzania later;
- Uganda may join only if the e-GP 2.0 machine contract converges semantically;
- Ghana/Namibia/Botswana do not justify pretending that public HTML/document portals are one reusable family.

## Testing and validation record

- **South Africa:** existing implementation and regression tests are present in `main`; merged PR #103 records live validation and CI success.
- **Other seven markets:** no code was authorized, therefore no connector/unit tests are claimed.
- **Public-source validation:** current official/public publisher pages and Open Contracting publisher records were checked for the decision-relevant gaps.
- **Local shell limitation:** direct repository cloning from the shell runtime failed because that environment could not resolve GitHub DNS. Repository inspection/writes were completed through the authorized GitHub connection. This is an environment limitation, not a source or repository failure.

## Official / publisher evidence used

### South Africa
- https://data.etenders.gov.za/Home/LearnMore
- https://ocds-api.etenders.gov.za/swagger/index.html
- https://data.etenders.gov.za/
- https://data.open-contracting.org/en/publication/57
- https://www.cidb.org.za/procurement/

### Kenya
- https://data.open-contracting.org/en/publication/56
- https://www.ppra.go.ke/
- https://tenders.go.ke/

### Uganda
- https://www.ppda.go.ug/
- https://data.open-contracting.org/en/publication/36
- https://egpuganda.go.ug/

### Zambia
- https://data.open-contracting.org/en/publication/58
- https://eprocure.zppa.org.zm/

### Ghana
- https://www.ghaneps.gov.gh/
- https://ppa.gov.gh/

### Namibia
- https://eprocurement.gov.na/

### Tanzania
- https://nest.go.tz/
- https://data.open-contracting.org/en/publication/68

### Botswana
- https://ipms.ppadb.co.bw/
- https://gov.bw/

## Final cell consequence

Coverage is not success. This queue does **not** justify seven new connectors merely because seven additional countries remain. The optimal current Africa posture is:

1. keep South Africa commercially available through the existing shared OCDS implementation with explicit incomplete-coverage caveats;
2. keep Kenya optional but legally gated;
3. keep Uganda, Zambia and Tanzania as technically valuable laboratories for shared-family/lifecycle learning;
4. keep Namibia on hold rather than misclassifying its problem as data absence;
5. remove Ghana and Botswana from current engineering despite useful portals, because machine/reuse economics do not pass the present opportunity-cost test.

No Master Queue changes are proposed by this cell.