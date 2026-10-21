# ObraSignal — International Massive Closure Campaign — 2026-08-25

Operational research evidence only. This document is **not** a source registry, market-scope registry, Master Queue, runtime switch or production authorization.

## Repository anchor

- campaign base: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`
- canonical strategic universe at that anchor: 135 markets = 14 BUILD + 31 SHARED + 28 HOLD + 62 REMOVE
- source registry at that anchor: 4 `active`, 17 `ready`, 1 `opt_in` (`PMP-LU`, legal YELLOW), 2 `planned/CREDENTIAL_REQUIRED` (`KR_KONEPS`, `CL_MERCADOPUBLICO`)
- `active` registry status is not synonymous with every source that is production-ready by gates, and neither is proof that a deployed production worker is currently ingesting that source.

## Exact live evidence from this campaign

### PR #243 first collector head `e766aa9aa05b0f204f5d7e4e878ac20581df8bba`

- ObraSignal Quality: SUCCESS
- International Mass Closure Probes #1: SUCCESS as evidence collector
- Dominican Republic DGCP Swagger: HTTP 200 JSON
- DGCP `/v1/procesos`: HTTP 200 JSON with explicit `page`, `pages`, `limit`, `totalResults`, `payload`
- DGCP `/v1/tablas/procesos`: HTTP 200 XLSX
- DGCP `/v1/tablas/contratos`: HTTP 200 XLSX
- New Zealand GETS current page: HTTP 200
- New Zealand `ExternalRSSFeed.htm`: HTTP 200 RSS 2.0, current open tenders/quotes
- Singapore GeBIZ opportunity listing: HTTP 200
- Australia AusTender root: HTTP 403 from normal GitHub-hosted runner

### PR #243 second collector head `4a220a2eaff5a6e56944bc379e81e66c838fa613`

- ObraSignal Quality: SUCCESS
- International Mass Closure Probes #2: SUCCESS as evidence collector
- Dominican DGCP transport results reproduced
- New Zealand GETS RSS result reproduced
- Singapore GeBIZ public listing reproduced
- Australia AusTender 403 reproduced
- Japan KAN-KO-JU API: HTTP 200 XML for `Category=2` (publisher-native construction), 7-day window, `SearchHits=700`; live sample exposed stable result key, external document URI, project name, source date, geography, organisation and issue date
- Japan portal terms page: HTTP 200
- Nigeria NOCOPO `/records`: HTTP 404
- Nigeria NOCOPO `/record-packages`: HTTP 404
- Nigeria NOCOPO licence page: HTTP 200

Source-side 4xx/timeout/zero-construction results are evidence. They are never treated as permission to bypass controls.

## High-value closure decisions

| Market / source | Current research decision | Exact remaining blocker / action | Owner / handoff |
|---|---|---|---|
| France / `FR_DECP` | **IMPLEMENTATION_READY** | canonical integration against latest main only | PR #230; source research closed |
| Chile / `CL_MERCADOPUBLICO` | **IMPLEMENTED / CREDENTIAL_REQUIRED** | obtain legitimate individual Mercado Público ticket; run existing live gate | merged #154 / canonical owner |
| Dominican Republic / `DO_DGCP` | **GATE_NARROWED materially** | complete deterministic construction prefilter over complete process/article transport; define snapshot/cursor atomicity; integrate with existing OCDS lifecycle normalizer | PR #197 / #225; handoff posted |
| Finland / `FI_HILMA` | **IMPLEMENTED / CREDENTIAL_REQUIRED** | self-service Hilma API portal subscription to `avp-read`, then bounded ContractNotices + PlanNotices live proof | PR #181; handoff posted |
| South Korea / `KR_KONEPS` | **CREDENTIAL_REQUIRED; lifecycle architecture proven** | legitimate service key, then live pagination/identity/change semantics | existing Korea implementation/owner; do not duplicate |
| Zambia / `ZM_ZPPA` | **TECHNICAL + RIGHTS SOURCE CLOSURE COMPLETE** | strategic WTP/economics only; source research is no longer the blocker | PR #228; handoff posted |
| Taiwan / PCC 7260/7264 | **RIGHTS GREEN FOR IMPLEMENTED SLICES** | broad live national TENDER-discovery route still unproven; current datasets are pre-tender/contract enrichment, not complete discovery | PR #228; handoff posted |
| Japan / KAN-KO-JU | **HOLD REOPEN EVIDENCE / TECH-LAB CANDIDATE** | completeness is explicitly not guaranteed; commercial redistribution/storage terms and economics/localisation still need product decision. Machine access, construction taxonomy and live current results are proven | no duplicate adapter; hand to international implementation/consolidation owner only if strategic HOLD is explicitly reopened |
| New Zealand / GETS | **MACHINE ACCESS CLOSED; LEGAL BLOCKER CONFIRMED** | written publisher permission for commercial indexed/republication use; current terms restrict automated collection and commercial/competitive republication | external action; no implementation |
| Australia / AusTender | **MACHINE ACCESS BLOCKED IN HOSTED ENVIRONMENT** | supported machine-readable live route that does not return 403 + specific reuse terms | HOLD; no bypass |
| Singapore / GeBIZ | **PUBLIC LISTING ACCESSIBLE; COMMERCIAL REUSE NOT PROVEN / RESTRICTED** | written permission or explicit open-data licence for commercial indexed opportunity reuse | HOLD; no implementation |
| Kenya / eGP/OCDS | **TECHNICALLY STRONG; LEGAL BLOCKER CONFIRMED** | OCDS-specific commercial licence/permission overriding/clarifying general eGP anti-data-mining/commercial-exploitation terms | HOLD |
| Indonesia / LKPP CKAN/SIRUP | **MACHINE-READABLE DATA EXISTS; RIGHTS UNKNOWN** | dataset-specific open licence + supported live tender route | HOLD; current datasets say `No License Provided` |
| Nigeria / NOCOPO | **RIGHTS GREEN; ENDPOINT CLAIM STALE** | discover/validate current supported OCDS export/download transport; old `/records` and `/record-packages` routes return 404; then freshness/completeness and WTP | HOLD; do not use stale endpoints |
| Mexico / Compras MX PAAASOP/PAOP | **PLAN REOPEN EVIDENCE STRONG** | exact current download transport + dataset-specific reuse licence; live incremental TENDER route still unresolved | HOLD; candidate `PROCUREMENT_PLAN` enrichment, not full market reopen yet |
| Saudi Arabia / Etimad | **API EXISTENCE PROVEN; DATASET MAPPING/TERMS NOT PROVEN** | identify `groupId` for procurement/tenders, actual supported server/API subscription path, terms/licence; do not infer from generic OpenData API name | HOLD |
| UAE / `AE_MOF_DPP` | **LIVE ACCESS WORKS; CONSTRUCTION SAMPLE/TAXONOMY NOT PROVEN** | validate publisher-native construction taxonomy or wider bounded sample; exact listing rights remain YELLOW | PR #235; handoff posted |
| Israel / `IL_GPA` | **LIVE ACCESS WORKS; CONSTRUCTION SAMPLE/TAXONOMY NOT PROVEN** | validate construction taxonomy/wider bounded sample; commercial reuse of current route remains YELLOW | PR #235; handoff posted |
| Oman / `OM_ESNAD` | **OPEN-DATA RIGHTS GREEN FOR FLOATED/AWARDED DATASETS** | map officially licensed dataset transport into existing identity if useful; separate Upcoming Tender HTML remains YELLOW | PR #235; handoff posted |
| Qatar / Ashghal | **LIVE TECH PASS; LEGAL BLOCKER** | written permission for commercial reuse/redistribution; current website terms are restrictive | PR #235 |
| Luxembourg / `PMP-LU` | **YELLOW CONFIRMED** | publisher/feed-specific commercial reuse confirmation; general public-sector reuse law is insufficient | existing source identity; no promotion |
| Brazil / PNCP PCA | **RIGHTS OPEN; ENDPOINT RELIABILITY BLOCKER** | ordinary-TLS OpenAPI + compact-date PCA update page with valid pagination from target environment | PR #242 evidence; no adapter before proof |
| Honduras / OCDS | **RIGHTS/CONTRACT STRONG; ENDPOINT REACHABILITY BLOCKER** | page1/page2/bulk successful in one bounded run; then current completeness/construction proof | PR #242 evidence; reuse shared OCDS |
| Peru / OECE | **MACHINE ACCESS BLOCKED** | ordinary permitted 2xx access in target environment; `/api/v1/files` and root returned 403 | PR #179/#242; no bypass |
| Guatemala / OCDS | **RIGHTS/SCHEMA STRONG; MACHINE ACCESS BLOCKED** | permitted stable official route without 403 | existing shared-family research; no bypass |
| Panama / V2 OCDS | **TLS GATE** | valid public certificate chain in target environment, then endpoint/pagination/reuse proof | PR #180; never weaken TLS |

## Rights closures

- Zambia official ZPPA OCDS publication is under ODC PDDL: copy/distribute/use/create/adapt allowed. Rights are not the reopen blocker.
- Taiwan PCC datasets 7260/7264 are under Taiwan Open Government Data License v1: commercial-purpose reuse/redistribution/derivatives are allowed for those exact datasets. Coverage remains the blocker.
- Nigeria NOCOPO licence is ODC PDDL. Rights are GREEN; current machine export route is the blocker.
- Finland Hilma explicitly positions `avp-read` as an open read interface for value-added services; credential acquisition is self-service.
- South Korea public-data KONEPS APIs are free/real-time/auto-approved and declare no licence restriction; credential/live proof remains.
- New Zealand GETS RSS is machine-accessible, but GETS terms restrict automated collection and commercial/competitive republication: do not treat RSS visibility as commercial reuse permission.
- Kenya eGP/OCDS technology does not itself establish commercial reuse permission; current general eGP terms prohibit data-mining/commercial exploitation without authorization.
- Indonesia open-data CKAN visibility does not equal reuse permission where metadata reports no licence.

## Stale claims corrected

1. **`PRODUCTION_ACTIVE = 26` was an over-broad operational shorthand.** Canonical `source_registry.py` has four sources whose registry `status` is literally `active`; 17 more are `ready`. `production_ready_sources()` and deployed ingestion state are different concepts and must not be collapsed.
2. **Dominican Republic sustainable completeness transport was previously under-proven.** Complete daily process/contract tables and a paginated `/procesos` API are now live-proven; remaining work is construction candidate selection + atomic cursor/snapshot integration, not discovery of a complete transport.
3. **Japan “no sufficiently unified machine-readable procurement route” is stale.** Official KAN-KO-JU API is live and returned 700 construction results in a 7-day window. Completeness/economics/rights-for-redistribution remain.
4. **New Zealand “machine access unproven” is stale.** GETS RSS is live; legal commercial reuse is the blocker.
5. **Nigeria rights uncertainty is stale.** ODC PDDL is explicit; old `/records` and `/record-packages` endpoint assumptions are the stale part.
6. **UAE/Israel MENA live failures are not machine-access failures.** They fetched official current rows/notices; the bounded sample produced no records admitted by the current construction classifier.
7. **Zambia rights are not unresolved.** ODC PDDL + exact-head live smoke close the source layer; WTP/economics alone keeps strategic HOLD.
8. **Taiwan rights are not unresolved for datasets 7260/7264.** Coverage semantics, not reuse rights, prevent treating them as broad TENDER discovery.

## Supersession / ownership

- Dominican/Uruguay overlapping implementation: use #197 as canonical implementation owner; #225 is exact-current-main combination evidence. Older #176/#196 remain evidence/history, not duplicate implementation candidates.
- Peru #179 + #242 are machine-access evidence; do not create a connector while 403 persists.
- Panama #180 owns TLS-gated research.
- France DECP #230 is the implementation-ready path.
- Finland #181 owns HILMA implementation.
- Taiwan/Zambia #228 owns those implementations.
- MENA #235 owns Oman/Qatar/UAE/Israel reconciliation; do not fork regional runtime/source identities.
- #242 remains exact evidence for Brazil/Honduras/Peru and is not a source registry.

## Next implementation batch — research recommendation only

1. **France DECP (#230)** — canonical integration/rebase/semantic conflict pass; no further source research needed.
2. **Dominican Republic (#197)** — replace broad N+1 discovery pressure with complete process/process-item snapshot/API candidate spine, publisher-native deterministic works prefilter, then hydrate only construction candidates through the existing OCDS lifecycle normalizer. Tests: full-page bounds, snapshot atomicity, duplicate/cursor safety, item-to-process identity, works false-positive/false-negative fixtures, lifecycle preservation, exact-current-main combination and live bounded gate.
3. **Finland (#181)** — after legitimate `avp-read` key: exact live ContractNotices + PlanNotices works smoke and paging/identity proof; no duplicate source.
4. **South Korea** — after legitimate KONEPS service key: existing TENDER path plus integrated contract-process API for plan/pre-spec/tender/award/contract lifecycle; prove `pageNo/numOfRows`, stable identity, change timestamp, and rate behavior.
5. **Japan TECH LAB only if strategic scope owner explicitly reopens HOLD** — stable source identity should derive from KAN-KO-JU, use `Category=2` as native construction admission, bounded date-overlap polling, Result `Key`/external document identity, XML parser, source completeness warnings, no claim of exhaustive national coverage, and no production promotion until redistribution/storage rights and economics are resolved.

## External action queue

- Chile: obtain legitimate Mercado Público ticket.
- Finland: create API portal account and subscribe to `avp-read`.
- South Korea: obtain legitimate KONEPS service key.
- New Zealand: request written GETS/MBIE permission for commercial indexing/caching/redistribution of RSS/opportunity metadata.
- Qatar: written commercial reuse permission if Ashghal source remains desired.
- UAE: publisher confirmation that the exact Current Business Opportunities dataset/surface is covered by open-data terms.
- Luxembourg: feed-specific PMP-LU commercial reuse confirmation.

## Safety boundary

NO MERGE. NO AUTO-MERGE. NO MASTER QUEUE CHANGE. NO PRODUCTION ACTIVATION. NO SECRET MUTATION. NO WAF/CAPTCHA/TLS/LOGIN BYPASS. No country/source state in this document is canonical until the existing owners and canonical governance incorporate the evidence.