# ObraSignal — APAC Next Wave Country Audit

**Audit date:** 2026-08-25  
**Cell:** Asia-Pacific Next Wave  
**Scope:** Japan, Australia, Singapore, Taiwan, New Zealand, Malaysia, Philippines, India  
**Canonical-state rule:** this research branch does **not** alter `CURRENT_ITEM_ID`, reorder `master_execution_queue.py`, promote a gated market, enable a source, or merge anything.

## Executive decision

The APAC queue does not justify eight new country connectors. The strongest new evidence is in **Taiwan**, where the Public Construction Commission publishes multiple daily, openly licensed, machine-readable procurement datasets with useful pre-tender signals and stable tender-case identity. Even there, the evidence collected in this pass proves a strong **early-signal slice**, not full national live-tender coverage.

Final cell classifications:

| Country | Classification | Engineering decision |
| --- | --- | --- |
| Japan | HOLD | Do not build a country connector; national + ministry + MLIT + local fragmentation and machine-reuse uncertainty remain material. |
| Australia | HOLD / LIMITED FEDERAL SLICE | AusTender has a useful federal machine route and Infrastructure Australia has excellent pipeline signals, but federal-only coverage is not enough to represent Australian construction and state expansion is costly. |
| Singapore | HARD BLOCK / HOLD | Excellent demand and planning signals; open award data exists, but GeBIZ live-notice reuse rights are not sufficiently green for commercial ingestion. |
| Taiwan | PREPARED EARLY-SIGNAL SLICE | Re-open technically for a bounded PCC open-data slice; do not call the country supported until live tender completeness and production endpoint behaviour are proven. |
| New Zealand | HOLD | Excellent FPO + infrastructure-pipeline semantics, but GETS detail access is registration-bound and the small-market test does not yet beat premium-market engineering. |
| Malaysia | HOLD | Public ePerolehan discovery exists, but no stable official machine feed/open-data reuse contract was proven; agency/public-works fragmentation remains material. |
| Philippines | TECH LAB / HOLD | Public notice + award lifecycle is visible, but the government roadmap itself shows unique IDs/open-data standardisation are still being upgraded through 2028. |
| India | HOLD / CENTRAL-SLICE CANDIDATE | Huge value and broad GePNIC/CPPP footprint, but no approved public machine route was proven that avoids manual/CAPTCHA-style portal dependence. Do not attempt all-India ingestion. |

No new shared family is justified by this pass. Similar output formats alone are not a family contract.

---

## Repository baseline — FACT

- `master_execution_queue.py` is the sole canonical queue and currently has `CURRENT_ITEM_ID = Q080_EVIDENCE_GRAPH_V1`.
- `Q020_SIGNAL_CONTRACT_V1` is DONE/PRODUCTION, so non-TENDER planning/forecast signals have a canonical persistence path.
- `Q070_SHARED_FAMILIES` is DONE/PRODUCTION and explicitly forbids abstraction based only on superficial JSON/XML similarity.
- `GLOBAL_MARKET_PORTFOLIO_VNEXT.md` currently places Japan, India, Australia and New Zealand among strategic HOLD options.
- `market_scope_registry.py` currently holds Australia, India, Japan, New Zealand, Philippines, Singapore and Taiwan behind explicit reopening conditions.
- `source_registry.py` contains no production-ready source for the eight countries in this cell.
- Existing shared families are TED/eForms and several distinct OCDS transports; none matches the APAC sources proven below.

## Research method

External research was bounded to official procurement portals, official open-data catalogues, procurement rules/manuals and official infrastructure sources, with a small competitor sanity check. No CAPTCHA, login bypass, private API or unsupported scraping was used.

Evidence labels below mean:

- **FACT** — directly supported by official source/repository evidence.
- **INFERENCE** — reasoned consequence of facts.
- **DECISION** — engineering/product choice for this cell.
- **BLOCKED** — required proof/access was not obtained.

---

# 1. JAPAN

## Executive decision

**CLASSIFICATION — HOLD**

### Commercial case

- **FACT:** Japan has large national/public-works demand and a mature government procurement regime.
- **FACT:** national procurement information is distributed across GEPS/procurement information services, ministry pages and public-works systems such as MLIT.
- **FACT:** official sources expose procurement plans, tenders, market/RFI-style activity and award/result material.
- **INFERENCE:** the opportunity is commercially material, but the value cannot be captured cheaply through one national construction connector.

### Primary official sources

- Government Procurement / GEPS ecosystem.
- MLIT electronic bidding and public-works procurement information.
- Ministry/Digital Agency procurement pages with procurement plan, tender and market-research/RFI material.
- JETRO Japanese Government Procurement for internationally covered notices.

### Signal types

`PROCUREMENT_PLAN`, `TENDER`, `MARKET_DIALOGUE`, `AWARD`/result evidence; `CAPITAL_PROJECT` through infrastructure programmes.

### Early signals

**STRONG semantically, FRAGMENTED technically.** Procurement plans and ministry market research/RFI activity are real early signals.

### Construction filter

Publisher/agency/public-works context is usable. A unified national construction taxonomy/API was not proven in this pass.

### Identity

**ADEQUATE to STRONG locally** where procurement case numbers exist; cross-system lineage is **UNKNOWN**.

### Access / rights

Public human access is proven. A sufficiently unified, stable machine route with commercial reuse rights for the needed construction scope was **not proven**.

### Foreign access

International/GPA notices are published and JETRO exposes English procurement information. Qualification remains procurement-specific; this does not establish broad frictionless access for foreign construction contractors.

### Shared/bespoke

No existing shared family fits. A bespoke national connector would still leave material MLIT/prefectural/municipal gaps.

### Engineering burden

**VERY HIGH** due to fragmentation, local-language metadata, publisher-specific lifecycle and likely multiple maintained sources.

### Known limitations

National source != whole-country public works. Prefectural/municipal coverage would materially increase connector count and maintenance.

### Final

Do not spend the next 100 engineering hours here. Reopen when a genuinely reusable national machine layer or a commercially valuable bounded slice is proven with green reuse rights and clear GTM.

---

# 2. AUSTRALIA

## Executive decision

**CLASSIFICATION — HOLD / LIMITED FEDERAL SLICE CANDIDATE**

### Commercial case

- **FACT:** Australian public/infrastructure construction is commercially attractive.
- **FACT:** Infrastructure Australia publishes a nationally significant pipeline/priority view that is valuable before tender.
- **FACT:** AusTender is the federal publication system; official guidance requires covered Commonwealth approaches to market and planned procurement publication there.
- **INFERENCE:** federal-only tender coverage misses too much state-delivered construction to represent the market as a whole.

### Primary official sources

- AusTender / Department of Finance.
- data.gov.au AusTender exports/RSS resources.
- Infrastructure Australia Infrastructure Priority List / pipeline evidence.
- State systems required for material construction breadth: NSW, Victoria, Queensland, Western Australia and others.

### Signal types

`TENDER`, `PROCUREMENT_PLAN`, `AWARD`/`CONTRACT` at federal level; `CAPITAL_PROJECT` nationally through Infrastructure Australia.

### Early signals

**STRONG.** Annual procurement plans and national infrastructure pipeline data provide useful forward demand.

### Construction filter

AusTender uses UNSPSC in planned procurements, approaches to market and contracts. This is preferable to keyword-only filtering.

### Identity

**STRONG federal / fragmented national.** Federal identifiers are useful; cross-state identity is publisher-specific.

### Access / rights

Official machine-readable federal data exists and historical contract datasets carry open-data licensing. A current live-opportunity RSS route is visible in the government data catalogue. Production reuse should still be contract-tested before enabling.

### Foreign access

Australia is covered by international government-procurement commitments; tender-specific qualification remains applicable.

### Shared/bespoke

No existing family fits. Do not build a fake `AustraliaConnector`. If reopened, use a federal connector plus explicitly separate state connectors/adapters.

### Engineering burden

- Federal slice: **MEDIUM**.
- Commercially representative construction coverage: **VERY HIGH** because state systems matter.

### Known limitations

State fragmentation is not optional for a construction-first product. Federal coverage alone is useful, but insufficient for an “Australia supported” claim.

### Final

Keep HOLD. Reopen a **federal-first limited slice** only if current live ATM feed rights/schema are live-proven and a paying segment values federal opportunities/pipeline intelligence without immediate state breadth.

---

# 3. SINGAPORE

## Executive decision

**CLASSIFICATION — HARD BLOCK / HOLD**

### Commercial case

- **FACT:** BCA forecasts a large multi-year construction demand base supported by major public infrastructure and housing projects.
- **FACT:** GeBIZ has thousands of current opportunities and a publisher-native Construction category.
- **FACT:** local third-party tender-alert/intelligence products already exist, so simple alerts are not enough differentiation.

### Primary official sources

- GeBIZ opportunities and awards.
- Ministry of Finance `data.gov.sg` Government Procurement via GeBIZ dataset.
- GeBIZ Indicative Government Procurement Opportunities.
- BCA construction demand / project pipeline information.

### Signal types

`TENDER`, `PROCUREMENT_PLAN`/`FORECAST`, `AWARD`; `CAPITAL_PROJECT` via BCA/infrastructure sources.

### Early signals

**STRONG.** GeBIZ indicative opportunities provide forward purchasing intentions; BCA adds sector/infrastructure foresight.

### Construction filter

GeBIZ native category `Construction` and subcategories are directly usable.

### Identity

**STRONG** at notice level via Tender No./agency references. Award dataset also exposes tender numbers.

### Access / rights

- **GREEN for the MOF open-data dataset:** public API/open-data licence and historical award-oriented fields are available.
- **RED/YELLOW for live GeBIZ tender reuse:** individual opportunity pages include restrictive reuse language around tender information/documents. Public visibility does not equal permission to reproduce/redistribute commercially.

### Foreign access

Foreign entities can obtain GeBIZ access through the non-UEN/GeBIZ-ID route. Public construction tenders can also require BCA contractor registration/workhead/grade and tender-specific qualifications.

### Shared/bespoke

No family fit. A dedicated GeBIZ scraper is **not authorised** while rights remain unresolved.

### Engineering burden

Technically **LOW/MEDIUM**; legal/rights burden **HIGH**. Easy engineering does not override bad rights.

### Known limitations

Open award data is not a substitute for reusable live tender discovery. A competitor can monitor public pages, but ObraSignal must satisfy its own commercial-reuse standard.

### Final

Remain HOLD. **LEGAL REVIEW REQUIRED** for live notice reuse. Continue using public indicative/BCA evidence only as research until a green machine/reuse contract is proven.

---

# Metrics after first 4 markets

- **MARKETS REVIEWED:** 4
- **MARKETS RETAINED AS OPTIONS:** 4
- **MARKETS PROMOTED TO ACTIVE SUPPORT:** 0
- **MARKETS REMOVED:** 0
- **NEW BESPOKE CONNECTORS:** 0
- **NEW SHARED FAMILIES:** 0
- **MARKETS PER NEW CONNECTOR FAMILY:** 0
- **ESTIMATED ENGINEERING HOURS AVOIDED VIA REUSE:** 0 (no legitimate new reuse family was found)
- **MAINTENANCE BURDEN ADDED:** 0
- **DECISION:** continue the second half because Taiwan/Philippines/India can materially change the APAC technical picture even if they do not become active markets.

---

# 4. TAIWAN

## Executive decision

**CLASSIFICATION — PREPARED EARLY-SIGNAL SLICE; NOT COUNTRY-SUPPORTED**

### Commercial case

Taiwan has a national public-procurement authority and unusually useful open pre-tender data. The commercial scale is below Japan/India/Australia but the engineering-to-signal ratio is materially better.

### Primary official sources — FACT

Public Construction Commission datasets on the Taiwan Government Open Data Platform include:

1. **Procurement notice** — procurement cases planned for public announcement in the current year for which tender notices have not yet been transmitted; fields include Tender case number, Tender name, Organization name, tendering method and scheduled tender year/month; XML; daily; Open Government Data License v1.0.
2. **Public viewing announcement** — tender documents available for public viewing before tender announcement; agency, tender number, project name, announcement count and date; XML; daily; open licence.
3. **Public Recruitment Announcement** — vendor/reference solicitation before public tender; agency, tender number, project, announcement count and date; XML; daily; open licence.
4. **Large procurement suppliers during performance period** — procurement nature, agency, tender number, project, award date, purchase amount, vendor IDs/names, winning amount and performance dates; XML; daily; open licence.
5. Additional GPA/public procurement datasets and classification/code datasets are available from the same official platform.

### Signal types

`PROCUREMENT_PLAN`, `PRIOR_INFORMATION`, `MARKET_DIALOGUE`, partial `TENDER`, `AWARD`, `CONTRACT`/performance evidence.

### Early signals

**VERY STRONG.** This is the best source-level early-signal finding in the eight-market cell.

### Construction filter

Official procurement nature/target classification fields exist; publisher-native codes should be used. Chinese native titles/agency names must be preserved. Translation belongs in presentation, not identity.

### Identity

**STRONG for bounded lineage.** Tender case number appears across multiple source types and is a credible plan/pre-tender/award join key. Cross-dataset collision/version behaviour still requires live tests.

### Access / rights

**GREEN at dataset catalogue level:** public, free, daily, Open Government Data License v1.0. Exact raw-resource endpoint behaviour must be live-validated per dataset before production use.

### Foreign access

Not fully audited in this pass. Do not infer broad construction eligibility from public data openness.

### Shared/bespoke

No current ObraSignal family fits. Do **not** create a generic XML family merely because several PCC resources are XML. A small PCC-specific adapter is justified only after exact resource contracts are captured.

### Implementation status

- **RESEARCH:** COMPLETE for the early-signal case.
- **CODE:** NOT IMPLEMENTED.
- **WHY NOT:** the browser catalogue proves dataset semantics/licensing, but exact raw endpoints/payloads for the complete bounded slice were not all successfully fetched in this environment; one PCC XML resource resolved to a `web.pcc.gov.tw` download endpoint but the live payload fetch failed. Implementing a guessed parser/URL would violate the source-contract standard.
- **NEXT SAFE STEP:** capture exact raw URLs and representative XML/JSON payloads for the four bounded PCC sources, then implement one source-specific PCC adapter with identity, incremental freshness, idempotency, update semantics and source regression fixtures.

### Engineering burden

**MEDIUM** for the bounded PCC slice, far below Japan/India whole-country coverage.

### Known limitations

The evidence does **not** prove full national live-tender coverage. Some tender datasets are GPA/partial or bounded by recency. Do not label Taiwan supported from the early-signal slice alone.

### Final

Taiwan is the first APAC market in this queue that merits concrete connector preparation once raw endpoint contracts can be live-proven. It still does not justify changing the canonical portfolio or queue from this parallel cell.

---

# 5. NEW ZEALAND

## Executive decision

**CLASSIFICATION — HOLD**

### Commercial case

- **FACT:** New Zealand Government Procurement states government procurement around NZ$51.5bn.
- **FACT:** mandated agencies publish Future Procurement Opportunities (FPOs) on GETS; FPOs are a rolling view covering at least the next 12 months.
- **FACT:** GETS is the main large-contract tender system; construction open-advertising threshold is high for new construction.
- **FACT:** the national infrastructure pipeline is a high-value forward signal.

### Signal types

`PROCUREMENT_PLAN`/`FORECAST`, `TENDER`, `AWARD`, `CAPITAL_PROJECT`.

### Early signals

**EXCELLENT semantically.** FPOs can link forward into RFx; infrastructure pipeline is especially valuable for construction intelligence.

### Construction filter

GETS has construction-specific procurement rules/fields. The pipeline provides sector/location/timing context.

### Identity

**ADEQUATE**, potentially strong when FPO→RFx links are present. Machine-readable identity contract was not proven.

### Access / rights

GETS allows public listing visibility, but detail access requires free registration/RealMe. No public production machine API/feed with green commercial reuse was proven in this pass. Pipeline data access/download can also require account access.

### Foreign access

GETS is free and supports open competition subject to tender-specific conditions and trade-agreement rules; registration is required for details/responding.

### Shared/bespoke

No current family fit. Do not automate registered account access without an explicit supported integration contract.

### Engineering burden

**MEDIUM**, but market size is small relative to the premium queue.

### Known limitations

High construction threshold means GETS does not represent every public construction opportunity. Strong early signal does not automatically clear the SMALL MARKET RULE.

### Final

Hold. Reopen if NZGP/GETS exposes a supported machine feed/API or if a paying customer/pipeline use case makes the bounded integration clearly superior to alternative engineering work.

---

# 6. MALAYSIA

## Executive decision

**CLASSIFICATION — HOLD**

### Commercial case

Malaysia has meaningful public construction demand and a national ePerolehan portal, but construction procurement also appears across ministries/agencies and public-works channels.

### Primary official sources

- ePerolehan official government procurement portal.
- MyProcurement-linked notices used by ministries.
- Agency procurement/tender pages.
- JKR/public-works sources where applicable.

### Signal types

Public portal proves `TENDER`/quotation discovery and award/result workflow. Early national procurement-plan machine data was not proven.

### Early signals

**WEAK/UNKNOWN** for a reusable national feed.

### Construction filter

ePerolehan has item/category codes and works notices. Supplier eligibility/registration categories are material.

### Identity

Notice/reference numbers exist; national cross-source lineage is **UNKNOWN**.

### Access / rights

Public opportunity pages exist. A stable official API/feed/bulk export and explicit commercial-reuse licence were **not proven**.

### Foreign access

Supplier registration/category requirements are material; construction tenders can have additional contractor/works eligibility. Do not assume a foreign entity can bid solely because a notice is public.

### Shared/bespoke

No family fit. HTML availability is not a machine-access contract.

### Engineering burden

**HIGH** relative to the proof available, with ongoing portal/agency fragmentation risk.

### Known limitations

No evidence-backed early-signal advantage sufficient to justify bespoke engineering now.

### Final

Hold until a machine-readable official route plus reuse rights are proven, preferably one that captures material works procurement without maintaining many agency-specific scrapers.

---

# 7. PHILIPPINES

## Executive decision

**CLASSIFICATION — TECH LAB / HOLD**

### Commercial case

PhilGEPS is nationally important and exposes public opportunities and recent award notices. Construction/public infrastructure demand is material.

### Primary official sources

- PhilGEPS public Open Opportunities / Recent Award interfaces.
- PhilGEPS Open Data analytics.
- Government PFM/Public Procurement reform roadmap.

### Signal types

`TENDER`, `AWARD`; annual procurement-plan reporting exists in PhilGEPS analytics. Contract-lineage quality is still evolving.

### Early signals

`PROCUREMENT_PLAN` potential exists, but a stable ingestion contract was not proven.

### Construction filter

PhilGEPS category/agency filters can identify construction-related notices. Publisher-native classification should be preferred over keywords.

### Identity

**ADEQUATE today, improving.** Award notices have an award notice number and reference the bid notice. However, the 2026–2028 reform roadmap explicitly identifies absence of mandatory unique contract IDs/procurement IDs and targets mandatory standardisation.

### Access / rights

Public human discovery is live. A stable, documented public production OCDS/API interface with green commercial-reuse rights was not proven.

### Foreign access

PhilGEPS includes foreign supplier registration flows. Tender-specific construction licensing/eligibility remains applicable.

### Shared/bespoke

Do not build an HTML scraper and do not call analytics pages an API. Keep as TECH LAB/HOLD until the official open-data/ID programme produces a supported contract.

### Engineering burden

**MEDIUM/HIGH** today; likely to fall materially if the planned open-data/ID standardisation lands.

### Known limitations

The official reform roadmap is itself evidence that current lineage/open-data standards are incomplete.

### Final

Do not rescue-loop the market now. Recheck when mandatory unique procurement/contract IDs and open-data publication are operational, not merely planned.

---

# 8. INDIA

## Executive decision

**CLASSIFICATION — HOLD / CENTRAL-SLICE CANDIDATE**

### Commercial case

India has enormous public-works demand. CPPP/eProcure and the GePNIC platform cover a large central-government/PSU footprint and many state/UT deployments, making a bounded central slice commercially interesting without pretending to ingest all India.

### Primary official sources

- Central Public Procurement Portal / eProcure.
- GePNIC deployments.
- GeM where relevant to procurement type.
- Ministry/PSU/rail/roads/public-works systems for specialised high-value slices.

### Signal types

`TENDER`, corrigenda/amendments and `AWARD` are publicly exposed by CPPP/eProcure. Procurement planning/infrastructure pipeline signals are dispersed by agency/programme.

### Early signals

**MEDIUM but fragmented.** National infrastructure programmes can be early, but no single procurement-plan data contract was proven for construction.

### Construction filter

Works/service categories and agency/programme context are available. A central public-works slice can avoid keyword-only matching.

### Identity

**ADEQUATE locally**, but all-India cross-system lineage is **WEAK/UNKNOWN**.

### Access / rights

Public notices are available, but no supported broad public machine API/feed with proven commercial reuse was found in this pass. The existing canonical reopening condition therefore remains unmet.

### Foreign access

The 2025 Department of Expenditure works manual confirms procurement-specific local-content/foreign participation constraints; foreign companies may in some cases need an Indian JV and eligibility is tender/policy specific. This lowers immediately addressable demand for foreign contractors.

### Shared/bespoke

Do not attempt an all-India connector. If reopened, start with a central CPPP/GePNIC slice only after a sanctioned machine-access path is documented.

### Engineering burden

- Central bounded slice: **HIGH**.
- Whole India: **EXTREME / irrational for current phase**.

### Known limitations

GePNIC software reuse across entities does not prove one shared public endpoint. Same platform != one ingest contract.

### Final

Hold. Preserve the central slice as the only rational entry strategy. Reopen on an official machine feed/API, sanctioned bulk route or partnership that removes portal automation risk.

---

# Metrics after 8 markets

- **MARKETS REVIEWED:** 8
- **ACTIVE-SUPPORT PROMOTIONS:** 0
- **PREPARED BOUNDED SLICES:** 1 (Taiwan early-signal PCC)
- **HOLD / HARD-BLOCK / TECH-LAB OPTIONS:** 7
- **REMOVE CURRENT PHASE:** 0 newly removed by this cell
- **NEW BESPOKE CONNECTORS:** 0
- **NEW SHARED FAMILIES:** 0
- **MARKETS PER NEW CONNECTOR FAMILY:** 0
- **ESTIMATED ENGINEERING HOURS AVOIDED VIA REUSE:** 0, because no genuine reusable transport contract was proven
- **ESTIMATED SPECULATIVE ENGINEERING AVOIDED BY NOT BUILDING PREMATURELY:** substantial but deliberately not assigned a fake precise number
- **COMMERCIAL POTENTIAL RETAINED:** all eight remain reconsiderable; no market is falsely activated
- **MAINTENANCE BURDEN ADDED:** 0

## Architecture conclusion

The queue produces **no evidence for an APAC mega-adapter**. Japan, Australia, Singapore, Taiwan, New Zealand, Malaysia, Philippines and India do not share a sufficiently uniform transport/lifecycle contract. The correct reuse outcome in this pass is therefore **no new family**.

Taiwan may justify a PCC-specific adapter after exact raw-resource contracts are captured. Australia may justify a federal AusTender slice later. India may justify CPPP/GePNIC central-only later. Those are separate publisher contracts until evidence proves otherwise.

## Quality / test status

- Repository architecture/state inspected: **YES**.
- Official-source research: **YES**.
- Rights/access audit: **BOUNDED; complete enough for decisions, not legal advice**.
- Code implemented: **NO**.
- Unit/integration/schema/idempotency tests: **NOT APPLICABLE — no code landed**.
- Live source validation: **PARTIAL** through public official pages/catalogues; not production-path validation.
- Taiwan raw resource live payload: **BLOCKED in this environment for the full bounded slice**; one official PCC XML resource URL resolved but live payload fetch failed.
- Canonical queue modified: **NO**.
- `CURRENT_ITEM_ID` modified: **NO**.
- Production source registry modified: **NO**.
- Merge performed: **NO**.

## Next safe engineering step

The next APAC engineering action with the best evidence/value ratio is **not** “build Japan” or “build all Australia”. It is:

1. live-capture exact raw PCC resource URLs and payload fixtures for Taiwan procurement notice, public viewing, public recruitment and performance-period award/contract datasets;
2. prove identity continuity on real `Tender case number` values across at least two lifecycle stages;
3. verify pagination/snapshot completeness and update semantics;
4. only then implement a PCC-specific early-signal connector behind the existing source production gates;
5. keep country support unpromoted until tender completeness is separately proven.

That step can be executed without touching the master queue state and without inventing an APAC shared family.