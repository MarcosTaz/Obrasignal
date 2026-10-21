# ObraSignal — High-Value MENA Expansion Wave

Date: 2026-08-25
Cell: MIDDLE EAST / HIGH-VALUE MENA
Status: RESEARCH EVIDENCE — NOT PRODUCTION COVERAGE

## Guardrails

- This work does not change `CURRENT_ITEM_ID`, the Master Queue, runtime wiring, or production source status.
- `PORTAL EXISTS != MACHINE-USABLE DATA` and `TECHNICAL ACCESS != COMMERCIAL REUSE RIGHTS` are enforced.
- No CAPTCHA, authentication, signed-session, private-API, rate-limit or anti-bot bypass was attempted.
- Existing canonical scope remains authoritative. On `main`, Saudi Arabia, Morocco and United Arab Emirates are HOLD markets; country-specific connector engineering is only allowed for canonical BUILD markets.
- Qatar, Oman, Israel, Bahrain and Kuwait were not found in the active BUILD/SHARED scope and therefore are not treated as supported.

## Executive decision

| Country | Cell classification | Addressable slice | Connector decision | Commercial potential | Engineering / maintenance |
|---|---|---|---|---|---|
| Saudi Arabia | HOLD; partnership route worth preserving | Central government Etimad + separate PIF/developer ecosystem | NO BUILD | VERY HIGH | HIGH / HIGH |
| United Arab Emirates | LIMITED MARKET SLICE | Federal first; Dubai and Abu Dhabi are separate surfaces | NO BUILD until feed/API + reuse rights | VERY HIGH | HIGH / HIGH if national; MEDIUM federal-only |
| Qatar | LIMITED MARKET SLICE | Ashghal construction/public works first | NO BUILD; TECH LAB candidate only | HIGH | MEDIUM / MEDIUM |
| Morocco | HOLD | National public-procurement portal | NO BUILD | MEDIUM-HIGH | MEDIUM / MEDIUM |
| Oman | TECH LAB | Central eTendering public slice | NO COMMERCIAL BUILD until rights + granular route close | MEDIUM-HIGH | LOW-MEDIUM if reusable family proves real |
| Israel | TECH LAB | Government Procurement Administration national portal | NO COMMERCIAL BUILD until supported machine route + rights close | HIGH | MEDIUM / MEDIUM |
| Bahrain | TECH LAB / LEGAL REVIEW REQUIRED | Central Tender Board | NO COMMERCIAL BUILD while reuse is unclosed | MEDIUM | LOW-MEDIUM if Oman family proves real |
| Kuwait | TECH LAB | CAPT central procurement + annual plans | NO COMMERCIAL BUILD until live supported route + rights close | HIGH | MEDIUM / MEDIUM |

No country in this wave is declared SUPPORTED, IMPLEMENTED, LIVE or PRODUCTION.

---

## 1. Saudi Arabia

### Executive decision

**CLASSIFICATION: HOLD (canonical); partnership/licensed route remains commercially interesting.**

### Public / SOE / developer split

- **Government procurement:** Etimad is the Ministry of Finance procurement platform and supports the government procurement lifecycle.
- **PIF / state-development companies:** NEOM, ROSHN, Qiddiya, Red Sea Global and Diriyah are giga-project investment vehicles in the PIF ecosystem. They are not to be represented as ordinary open central-government tenders.
- **Private/restricted procurement:** supplier portals, invitations, prequalification and developer-specific procurement must remain semantically separate from Etimad public notices.

### Addressability

Saudi Government Tenders and Procurement Law states that government entities deal with licensed persons and places a material condition on dealing with foreign persons for supplies/works in the Kingdom where qualified local supply exists. The law also gives priority to local SMEs, local content and listed companies. Contractor classification covers construction/building among the targeted sectors and evaluates financial and technical capacity.

**Foreign access state:** CAN VIEW / CAN REGISTER: partial evidence; CAN BID: conditional; NEEDS CLASSIFICATION: material for construction; LOCAL-CONTENT BURDEN: material; project-specific prequalification and guarantees remain possible.

### Machine access and rights

Etimad has a developer/API portal, but the live API products located in this audit are contract/financial intelligence products (for example contract inquiry for banks/financing use cases), not an authorized broad tender-discovery feed. Therefore the canonical reopening condition is **not met**.

### Signal value

Potential signal classes: PROCUREMENT_PLAN, PREQUALIFICATION, TENDER, AWARD, CONTRACT, CAPITAL_PROJECT. Giga-project announcements remain CAPITAL_PROJECT signals unless a procurement event is independently evidenced.

### Sources

- Ministry of Finance — Government Tenders and Procurement Law: https://mof.gov.sa/Knowledgecenter/newGovTendandProcLow/Pages/Sec01.aspx
- Etimad Developer Portal: https://portal.etimad.sa/en-us/developer
- Contractor classification authority (Balady): https://co.balady.gov.sa/ar/node/3729
- PIF giga-project evidence: https://www.pif.gov.sa/en/our-investments/giga-projects/

### Final

IMPLEMENTED: NO. TESTED: research/source validation only. LIVE VALIDATED: official public pages located; no production ingestion path validated. PR CODE: none.

---

## 2. United Arab Emirates

### Executive decision

**CLASSIFICATION: LIMITED MARKET SLICE — federal-first is economically rational, national coverage is not one connector.**

### Fragmentation

- **Federal:** Ministry of Finance Digital Procurement Platform / Federal Supplier Register.
- **Dubai:** separate official iSupplier procurement portal.
- **Abu Dhabi:** separate Abu Dhabi Government Procurement Gate.
- Major public utilities and state-linked entities can add further supplier/procurement surfaces.

### Foreign contractor addressability

The Federal Supplier Register explicitly allows a **Foreign Supplier: company located outside UAE without a local branch in UAE**. Qualified suppliers can browse current federal open tenders and submit proposals. Registration requires supplier qualification and UAE PASS workflow requirements.

This is strong evidence that the **federal slice is commercially addressable**, but it is not evidence that every Dubai/Abu Dhabi/public-entity opportunity is covered by the same route.

### Technical decision

The public Ministry pages expose business-opportunity counts and supplier workflow, but this audit did not verify a supported public tender-discovery API/feed with redistribution terms. The canonical HOLD reopening condition on `main` therefore remains false.

### Sources

- Federal Supplier Register / foreign supplier eligibility: https://mof.gov.ae/en/services/register-suppliers-in-the-federal-supplier-register/
- Federal Digital Procurement Platform: https://mof.gov.ae/en/public-finance/government-procurement/digital-procurement-platform/
- Dubai iSupplier: https://login-isupplier.dubai.gov.ae/
- Abu Dhabi Government Procurement Gate: https://www.adgpg.gov.ae/

### Final

IMPLEMENTED: NO. TESTED: research/source validation only. LIVE VALIDATED: official public federal/Dubai/Abu Dhabi surfaces located; no production ingestion path validated.

---

## 3. Qatar

### Executive decision

**CLASSIFICATION: LIMITED MARKET SLICE — Ashghal public works is the high-value first slice; do not call it national coverage.**

### Primary construction source

Ashghal exposes live e-Tender listings with open, closed and archived tenders. On 2026-08-25 the official page exposed 39 open, 183 closed and 439 archived e-tenders, including roads, drainage, buildings and explicit `PRE` procurement/prequalification-style entries.

### Addressability

Ashghal company registration accepts a company country and a commercial registration document from the respective country. It enables profile management, tender-document purchasing and tender notifications, but explicitly states registration does not guarantee engagement. Ashghal points companies to the Ministry of Finance unified procurement site (Monaqasat) for government registration/classification before tender participation.

**Foreign access state:** CAN VIEW: YES; CAN REGISTER: evidence supports foreign-company profiles; CAN BID: conditional; NEEDS CLASSIFICATION / PREQUALIFICATION: YES for relevant procurement.

### Technical route

Ashghal HTML is useful and current, but no documented public API/feed or commercial reuse licence was verified. Monaqasat also did not yield a supported machine interface in this audit. A scraper is not justified under current project rules.

### Sources

- Ashghal e-Tenders: https://www.ashghal.gov.qa/en/Tenders/Pages/erptenders.aspx
- Ashghal tender notification / Monaqasat classification: https://www.ashghal.gov.qa/en/Tenders/Pages/TenderNotification.aspx
- Ashghal company registration: https://www.ashghal.gov.qa/en/Pages/CompanyRegisteration.aspx

### Final

IMPLEMENTED: NO. TESTED: research/source validation only. LIVE VALIDATED: public listing freshness verified. PRODUCTION PATH: NO.

---

## 4. Morocco

### Executive decision

**CLASSIFICATION: HOLD (canonical).**

The Trésorerie Générale du Royaume describes the Portail Marocain des Marchés Publics as publishing procurement forecasts/programmes, calls for tenders, tender documents, results, excluded suppliers and audit information. That is excellent semantic coverage for ObraSignal, especially PROCUREMENT_PLAN -> TENDER -> RESULT lineage.

However, this audit did not locate a supported public API/feed or a commercial-reuse licence that satisfies the canonical reopening condition. Browser-visible national coverage is therefore not enough to authorize a connector.

### Sources

- TGR service description: https://www.tgr.gov.ma/
- Portail Marocain des Marchés Publics: https://www.marchespublics.gov.ma/

### Final

IMPLEMENTED: NO. TESTED: research/source validation only. LIVE VALIDATED: portal/service evidence; machine/reuse gate remains red.

---

## Four-country checkpoint

DECISION estimates, not production facts:

- MARKETS REVIEWED: 4
- BUILD NOW: 0
- PARTNERSHIP ROUTE MATERIAL: 1 (Saudi state-development/private ecosystem)
- HOLD (canonical): Saudi Arabia, Morocco, UAE remains canonical HOLD despite federal slice value
- MARKET SLICES SELECTED: 2 (UAE federal; Qatar Ashghal)
- NEW CONNECTORS: 0
- NEW SHARED FAMILIES: 0
- AUTHORIZED ENGINEERING HOURS NOW: 0 connector hours
- ENGINEERING IF RIGHTS/MACHINE GATES CLOSED: roughly 135–245h across the four, before production hardening
- COMMERCIAL POTENTIAL RETAINED: very high in Saudi/UAE; high Qatar; medium-high Morocco
- COMMERCIAL POTENTIAL REJECTED/DEFERRED DUE ACCESS: material in all four

---

## 5. Oman

### Executive decision

**CLASSIFICATION: TECH LAB — small-market rule passes only because data transparency and GCC reuse leverage are unusually strong.**

The official eTendering dashboard exposes floated/opened/awarded/cancelled counts, an `International` dimension and registered-company counts. During this audit it showed roughly 21.3k registered companies, ~4.15k international companies, ~2.3k floated tenders with ~140 international, and more than 30k awards with hundreds tagged international. The portal labels part of the dashboard `Open Data Graphical Report`.

This is meaningful proof of foreign participation and lifecycle/award intelligence. It is **not** proof that granular notice data is licensed for commercial SaaS ingestion. No supported granular API/feed or explicit reuse licence was verified.

### Shared-family hypothesis

Oman and Bahrain expose strikingly similar eTendering dashboard semantics and UI patterns. That is a **hypothesis for a transport-family Tech Lab**, not a `MENAConnectorBase` decision. Reuse must be proven at request/response, identity, pagination and update-semantics level before any family is created.

### Source

- Oman Tender Board eTendering dashboard: https://etendering.tenderboard.gov.om/product/publicDash

### Final

IMPLEMENTED: NO. TESTED: live public-dashboard research validation. LIVE PRODUCTION INGESTION: NO. RIGHTS: LEGAL REVIEW REQUIRED.

---

## 6. Israel

### Executive decision

**CLASSIFICATION: TECH LAB — unusually strong early-signal semantics justify deeper technical/legal validation.**

The Government Procurement Administration portal exposes a very large searchable corpus and distinguishes **RFI**, **Public Tender**, **Intent to Contract** and **Exempt** records. Records expose publisher, serial ID, process ID, publication/update dates and deadlines. This is unusually valuable for ObraSignal because it naturally separates early information requests and intent notices from tenders.

Official trade-procurement material also identifies the Government Procurement Administration site as a publication route for procurement notices and award information. Foreign-supplier rules exist and can impose industrial-cooperation/offset obligations in covered procurements, so `FOREIGN CONTRACTOR ACCESS` cannot be represented as an unrestricted boolean.

No officially documented public API/feed or explicit commercial reuse licence was verified during this audit. Hebrew-language source text should remain native; translation belongs in presentation, not the connector core.

### Sources

- Government Procurement Administration general search: https://mr.gov.il/ilgstorefront/en/search/general-search
- Tender-only search / RFI + public tender evidence: https://mr.gov.il/ilgstorefront/en/search/?s=TENDER
- Government procurement publication evidence: https://www.gov.il/

### Final

IMPLEMENTED: NO. TESTED: live public search semantics validated. LIVE PRODUCTION INGESTION: NO. RIGHTS/MACHINE ROUTE: LEGAL + TECH REVIEW REQUIRED.

---

## 7. Bahrain

### Executive decision

**CLASSIFICATION: TECH LAB / LEGAL REVIEW REQUIRED.**

Bahrain passes the small-market rule on data quality and regional leverage, not on market size alone. The official Tender Board dashboard on 2026-08-23 showed 37 published, 1,372 to-be-opened, 3,305 opened and 988 cancelled tenders; 14,691 registered suppliers including 3,675 international suppliers; and construction tenders visible in the public list. Prequalification is a first-class portal concept.

The dashboard footer states `CopyRight © All Right Reserved`. That is a material rights warning: public readability is not a green commercial-reuse licence. No public supported API/feed was verified.

### Source

- Bahrain eTendering / Tender Board: https://etendering.tenderboard.gov.bh/Tenders/publicDash

### Final

IMPLEMENTED: NO. TESTED: live public-dashboard research validation. LIVE PRODUCTION INGESTION: NO. RIGHTS: NOT GREEN.

---

## 8. Kuwait

### Executive decision

**CLASSIFICATION: TECH LAB — high early-signal potential, but machine/reuse path not closed.**

CAPT is a central procurement authority. Its published procurement law requires government entities to prepare and publish annual plans and a schedule of tenders/prequalifications at least 90 days before launch, creating potentially valuable `PROCUREMENT_PLAN` / `FORECAST` signals. The law also allows external/international public tenders and foreign bidders subject to registration/qualification conditions.

CAPT exposes tender and winning-bid pages, including organization, tender reference, subject, winner and meeting date. Foreign contractor registration requires attested company documentation, bilingual Arabic/English material and authorization formalities.

The audit did not establish a supported live API/feed, reliable incremental semantics or commercial reuse licence. Search results also surfaced pre-production CAPT URLs, so production endpoint stability must be independently verified before any connector lab is promoted.

### Sources

- CAPT procurement law / rules: https://capt.gov.kw/
- CAPT foreign contractor registration: https://files.capt.gov.kw/static/docs/foreign-registration-docs/English.pdf
- CAPT winning-bid evidence: https://preprod.capt.gov.kw/en/tenders/winning-bids/

### Final

IMPLEMENTED: NO. TESTED: research/source validation. LIVE PRODUCTION INGESTION: NO. RIGHTS/MACHINE ROUTE: OPEN.

---

## Competition and differentiation

The GCC is not an empty intelligence market. ProTenders markets construction intelligence and eTendering across UAE, Saudi Arabia, Qatar, Bahrain, Oman and Kuwait, including project participants and contacts. Ventures Onsite tracks projects from concept to completion across MEA. BNC markets a project-intelligence layer with live projects, decision makers and tender-stage signals.

Therefore `show tender listings` is not a viable MENA differentiation strategy. ObraSignal's defendable direction is:

1. official-source provenance and exact signal semantics;
2. early signals (plan, RFI, intent, prequalification) kept distinct from tenders;
3. award/contract lineage;
4. foreign-contractor barrier intelligence;
5. evidence-backed decision support rather than generic project directories.

Reference competitors:
- ProTenders: https://www.protenders.com/solutions/solutions-for-contractors
- Ventures Onsite: https://www.venturesonsite.com/projects/
- BNC Network: https://beta.bncnetwork.net/products/project-intelligence

---

## Final cell metrics

DECISION estimates:

- MARKETS REVIEWED: 8/8
- BUILD NOW: 0
- SHARED COVERAGE: 0
- LIMITED MARKET SLICE: UAE federal; Qatar Ashghal
- PARTNERSHIP / LICENSE ROUTE WORTH PRESERVING: Saudi developer/PIF ecosystem; potentially Bahrain/Oman if official reuse or licensing is offered
- TECH LAB: Oman, Israel, Bahrain, Kuwait
- HOLD: Saudi Arabia, Morocco; UAE remains canonical HOLD until its existing reopen condition is met
- NEW CONNECTORS: 0
- NEW SHARED FAMILIES: 0 (Oman/Bahrain is a hypothesis only)
- ESTIMATED ENGINEERING BURDEN IF ALL GATES LATER CLOSE: ~230–390h before full production hardening, heavily dependent on whether Oman/Bahrain actually share a transport family
- MAINTENANCE BURDEN: HIGH for national UAE/Saudi fragmented coverage; MEDIUM Qatar/Israel/Kuwait; potentially LOW-MEDIUM Oman/Bahrain if a true shared family is proven
- COMMERCIAL POTENTIAL RETAINED: very high Saudi/UAE; high Qatar/Israel/Kuwait; medium-high Morocco/Oman; medium Bahrain

## Reopen / next safe actions

1. **Saudi:** only reopen connector engineering on an Etimad-authorized broad discovery product/feed or a negotiated licensed source; keep developer/PIF intelligence separate.
2. **UAE:** ask MoF for documented machine-access/reuse terms for federal tender discovery before engineering; do not expand to Dubai/Abu Dhabi until the federal economics are proven.
3. **Qatar:** seek official permission/feed/export for Ashghal/Monaqasat; preserve PRE/EOI semantics.
4. **Morocco:** reopen exactly on the existing canonical API/feed + commercial-reuse condition.
5. **Oman/Bahrain:** perform a bounded family proof only after rights clarification; compare transport, pagination, IDs, update semantics and detail endpoints.
6. **Israel:** request/document an official machine interface or sanctioned export and reuse terms; if available, this becomes the strongest early-signal Tech Lab in the wave.
7. **Kuwait:** verify production CAPT URLs and whether annual procurement plans/tender/award tables have a sanctioned structured export/API.

## Self-review

- Construction activity was not equated with addressable procurement.
- PIF giga-projects were not called open government tenders.
- UAE federal coverage was not called national coverage.
- Registration/classification/local-content/prequalification burdens were retained.
- No public HTML page was treated as proof of commercial reuse rights.
- No bespoke connector was proposed solely because a prestigious market is large.
- Partnership/licensing remains an explicit route where engineering cannot lawfully manufacture access.
