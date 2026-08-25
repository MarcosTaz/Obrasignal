# ObraSignal — MENA High-Value Wave 2 Adversarial Review

Date: 2026-08-25
Scope: Saudi Arabia, United Arab Emirates, Qatar, Morocco, Oman, Israel, Bahrain, Kuwait
Status: RESEARCH / DECISION EVIDENCE ONLY — NOT PRODUCTION COVERAGE

## Purpose

This document is a reviewer-style hardening pass over `MENA_HIGH_VALUE_WAVE2_20260825.md`. It does not change canonical market scope, the Master Queue, runtime wiring or source readiness. It exists to make access, rights, signal semantics and foreign-contractor barriers explicit enough that a future engineer cannot mistake a readable portal for a production-safe data source.

## Canonical boundary

- `CURRENT_ITEM_ID` is not changed.
- No market is promoted to BUILD/SHARED/PRODUCTION by this branch.
- No connector, scraper or private endpoint is introduced.
- Browser-visible data is not treated as permission for commercial storage, redistribution or SaaS reuse.
- `LIVE SOURCE CHECKED` below means an official/public source was reachable and semantically inspected. It does **not** mean production ingestion was validated.

## Gate matrix

| Country | Cell decision | Primary slice | Source access | Commercial reuse | Foreign access | Strongest signals | Production connector gate |
|---|---|---|---|---|---|---|---|
| Saudi Arabia | HOLD | Etimad central government; PIF/developers separate | PUBLIC search + API portal with subscription/approval for products | NOT CLOSED for broad tender discovery | CAN VIEW; bid/works conditional; classification/local-content material | TENDER; AWARD/CONTRACT; potential plans; CAPITAL_PROJECT only for giga-project announcements | RED — no authorized broad tender-discovery API/feed proven |
| UAE | LIMITED MARKET SLICE, canonical HOLD | Federal first | PUBLIC information; supplier/account workflow for procurement platform | NOT CLOSED for SaaS discovery/redistribution | Foreign supplier category explicitly supported federally; qualification required | TENDER; CONTRACT workflow | RED — no supported public discovery feed/API + reuse terms proven |
| Qatar | LIMITED MARKET SLICE | Ashghal public works | PUBLIC listings/project briefs; supplier registration; Monaqasat classification dependency | NOT CLOSED | CAN VIEW; foreign company profile evidence; bid conditional on classification/PQ | **PROCUREMENT_PLAN / project launch list; PREQUALIFICATION/EOI; TENDER; AWARD** | RED for production; high-value Tech Lab candidate only |
| Morocco | HOLD | National public-procurement portal | PUBLIC portal | NOT CLOSED | Conditional/registration rules not reduced to a boolean | PROCUREMENT_PLAN; TENDER; RESULT/AWARD-style publication | RED — canonical API/feed + commercial-reuse reopening condition not met |
| Oman | TECH LAB | Central eTendering | PUBLIC dashboard; account-based tendering | NOT CLOSED | Strong official evidence of international registrations/tender lifecycle | TENDER; AWARD; subcontract tender visibility | RED — no sanctioned granular API/export + explicit reuse terms proven |
| Israel | TECH LAB | Government Procurement Administration | PUBLIC searchable portal | NOT CLOSED | Foreign supplier participation possible; covered procurements may trigger industrial-cooperation obligations | **RFI; PUBLIC TENDER; INTENT TO CONTRACT; EXEMPT** | RED — no officially documented machine feed/API + reuse terms proven |
| Bahrain | TECH LAB / LEGAL REVIEW | Central Tender Board | PUBLIC dashboard/listings; registered supplier system | NOT GREEN; portal states all rights reserved | Strong official evidence of international suppliers | TENDER; PREQUALIFICATION; lifecycle statuses | RED — rights warning + no supported public feed/API proven |
| Kuwait | TECH LAB | CAPT central procurement | PUBLIC law/tender/award pages; registration workflow | NOT CLOSED | Foreign contractor registration route exists with attestation/bilingual requirements | **90-day PROCUREMENT PLAN / PREQUALIFICATION forecast; TENDER; WINNING BID** | RED — production endpoint/feed/incremental/reuse not closed |

## Country corrections and strengthened evidence

### Saudi Arabia

The Etimad Developer Portal is real and production-oriented: it allows users to explore APIs, obtain keys, subscribe to products, use Swagger and request production access. Its stated target audience includes private-sector suppliers and contractors. However, the concrete live products located during this review are contract/financial inquiry products such as `Contracts Plus`, where the query model is beneficiary/CR/contract-oriented. That is materially different from a broad tender-discovery feed.

Therefore the canonical reopening condition remains false. The existence of an API platform is **not** evidence that ObraSignal can ingest the full tender-discovery corpus. Local-content preference rules remain a material commercial barrier. Giga-project/developer announcements remain `CAPITAL_PROJECT` unless a procurement event is separately evidenced.

### United Arab Emirates

Federal addressability is stronger than a generic GCC assumption: the Ministry of Finance explicitly defines a `Foreign Supplier` as a company located outside the UAE without a local branch, and qualified suppliers can browse federal open tenders and submit proposals. This supports a **federal-first commercial slice**.

It does not solve machine access or rights. Registration/qualification is an account workflow, and the federal surface cannot be generalized to Dubai, Abu Dhabi or state-linked entities. National UAE coverage remains a fragmentation problem, not one connector.

### Qatar — upgraded early-signal finding

Ashghal is the strongest early-signal slice found in this GCC wave. The official tender navigation exposes a **`List of Projects to be launched in 2026` split by First/Second/Third/Fourth Quarter**. This must be modeled, if ever licensed for ingestion, as `PROCUREMENT_PLAN` or `CAPITAL_PROJECT/FORECAST` depending on record semantics — never as `TENDER`.

Ashghal also exposes first-class `Pre-Qualifications - Expression of Interests` surfaces and live e-tender listings. On 2026-08-25 the e-tender page showed 39 open, 183 closed and 439 archived records. Project briefs can expose `Company Nationality`, vendor grade and classification/activity requirements; examples include `Company Nationality: ALL`, while historical records also show `Qatari only`, proving eligibility is opportunity-specific rather than a country-level boolean.

A future sanctioned connector could therefore support a useful lineage:

`PROJECT LAUNCH PLAN -> PREQUALIFICATION/EOI -> TENDER -> AWARD`

but only after official machine-access/reuse permission is closed.

### Morocco

The TGR description remains valuable because it explicitly covers publication of forecast procurement programmes, competition notices, results, opening-minutes extracts and completion reports. Semantically this can support richer lifecycle intelligence than tender listings alone.

No supported public API/feed plus commercial-reuse permission was proven in this review, so the existing HOLD gate remains correct.

### Oman

The official eTendering dashboard demonstrates material international participation and lifecycle depth. During the review the public dashboard showed approximately 21.3k registered companies, about 4.1k international companies, thousands of floated/opened records and more than 30k awards, with separate `International` counts. It also labels a dashboard area `Open Data Graphical Report`.

`Open Data Graphical Report` is **not interpreted as an open-data licence**. No granular machine interface or explicit commercial-reuse licence was proven. Oman remains a good low-burden Tech Lab candidate only if sanctioned access is obtained.

### Israel

The official procurement search provides unusually clean source semantics. Current results expose categories including `RFI`, `Public Tender`, `Intent to Contract` and `Exempt`, plus publisher, serial, process, published, updated and deadline fields. This is a strong fit for provenance-first early-signal intelligence and update identity.

Foreign-supplier participation cannot be treated as unrestricted: official industrial-cooperation regulations require covered foreign suppliers winning certain tenders to undertake industrial cooperation, with tender-specific obligations and plans. Native Hebrew should remain source truth; translation belongs above the connector layer.

### Bahrain

The official dashboard showed 14,691 registered suppliers and 3,675 international suppliers in the live review, together with published/opened/cancelled tender states and prequalification as a portal concept. This is strong evidence of foreign supplier presence and centralization.

The same official page states `CopyRight © All Right Reserved`. This is an explicit rights warning. Until the Tender Board grants or publishes commercial reuse rights, ObraSignal must not interpret public readability as authorization to store/redistribute the dataset commercially.

### Kuwait

CAPT's procurement law creates a high-value early-signal advantage: Article 88 requires public authorities to prepare a schedule of tenders and qualifications at least **90 days before** offering them, with a profile, subject to implementing rules. This is a genuine `PROCUREMENT_PLAN/FORECAST` opportunity if a sanctioned structured publication route can be obtained.

Foreign contractor registration is real but burdensome: CAPT requires an attested commercial licence, authorization/signatory documentation and Arabic/English material. The official law also contains contractor-classification constraints. Winning-bid pages expose organisation, tender reference, subject, winner and meeting date, but observed search results included a `preprod` hostname; that cannot be promoted to a production ingestion dependency without endpoint verification.

## Engineering decision

### Do not build now

No country in this wave currently satisfies all three gates required for a production connector:

1. canonical scope authorizes country-specific engineering;
2. a supported/sanctioned machine route is proven; and
3. commercial reuse/storage/redistribution rights are green.

Creating HTML scrapers here would convert market enthusiasm into maintenance and legal debt. That fails the 100-hour test and the project's source-rights rules.

### Reusable-family decision

Do **not** create `MENAConnectorBase`.

Oman and Bahrain remain only a shared-family hypothesis because their dashboards are visually/semantically similar. A real family requires proof of common transport, request/response schema, stable identity, pagination, update timestamps/state transitions and rights. Similar HTML is insufficient.

### Highest-value unlock order

1. **Qatar / Ashghal** — ask for sanctioned structured access to quarterly launch plans + PRE/EOI + tender + award data. This is the best early-signal product fit.
2. **UAE federal** — obtain MoF machine-access and commercial-reuse terms for tender discovery; prove federal economics before adding Dubai/Abu Dhabi.
3. **Israel** — request sanctioned export/API and reuse terms; source semantics are exceptionally strong.
4. **Saudi Arabia** — determine whether Etimad can license/authorize a broad tender-discovery API product; do not substitute contract-financing APIs.
5. **Oman/Bahrain** — clarify rights first, then run one bounded transport-family proof.
6. **Kuwait** — verify production CAPT publication endpoints and structured availability of the Article 88 planning layer.
7. **Morocco** — reopen only when the existing canonical feed/API + commercial-reuse condition is actually met.

## Verification record

- Official source pages rechecked on 2026-08-25.
- No authentication/CAPTCHA/private API/rate-limit bypass attempted.
- No connector code added.
- No source registry entry added.
- No market-scope registry change made.
- No Master Queue change made.
- No claim of production ingestion made.
- Existing PR head CI before this hardening commit: `ObraSignal Quality` run 1210 = SUCCESS.
- This document changes evidence only; the new head must be checked again after commit.

## Final reviewer conclusion

The original eight-country classifications survive adversarial review. The material change is that **Qatar/Ashghal should be treated as the strongest early-signal Tech Lab candidate in this wave**, because the official source exposes quarterly project-launch planning plus PRE/EOI plus tender layers. UAE federal remains the strongest immediately addressable foreign-supplier slice. Israel is the strongest taxonomy/identity candidate. Saudi retains the largest upside but remains access-gated. Oman/Bahrain have the best regional-reuse hypothesis but unresolved rights. Kuwait has an unusually valuable statutory 90-day forecast concept but an unresolved production data route. Morocco remains a correct HOLD.
