# ObraSignal Country Launch Priority v1

Status: **RESEARCH BASELINE — NOT LAUNCH AUTHORIZATION**  
Last reviewed: **2026-08-26**  
Upstream exact-head consumed: **66d43f6fd51cf9cea08016dad335aaa04b711a24**

This dossier belongs to the **Global Market Entry, Localization & Country Launch Automation** layer. Source legality, source technical truth and BUILD/SHARED/HOLD/REMOVE remain owned by Global Market Expansion. A country marked `LAUNCH_NOW` below means **advance launch research/localization now**, never production launch authorization.

## Material upstream boundaries

- Commercial portfolio: 14 BUILD + 31 SHARED; TECH_LAB/HOLD/REMOVE are not launch preparation candidates.
- BUILD does not imply source-production activation.
- Brazil remains launch-blocked by the upstream live PNCP production-path gate.
- Chile remains launch-blocked until a real individual Mercado Público production ticket exists.
- Canada is federal-first only; CanadaBuys does not imply provincial/municipal completeness.
- United States is SAM.gov federal-first only; current support does not imply SLED completeness.
- TED/eForms shared coverage does not imply complete national or below-threshold coverage in European countries.

## First country-launch priority matrix

| Priority | Country | Upstream | Launch state | Why advance now | Primary risk | Decision |
|---:|---|---|---|---|---|---|
| 1 | Portugal | BUILD | LAUNCH_RESEARCH | BASE + TED are explicit active/ready product inputs; lowest language/support distance; upstream already calls the market validated | cheap incumbent alerting means raw alerts have weak pricing power | LAUNCH_NOW |
| 2 | Spain | BUILD | LAUNCH_RESEARCH | PLACSP + TED explicit; large works market and meaningful national/sub-threshold workflow | free official discovery + low-cost alert products; must win on relevance and bid/no-bid workflow | LAUNCH_NOW |
| 3 | United Kingdom | BUILD | LAUNCH_RESEARCH | rich lifecycle and forward pipeline notices; English launch; clear high-WTP intelligence category | mature incumbents; current ObraSignal coverage must not be marketed as every UK portal | LAUNCH_NOW |
| 4 | France | BUILD | LAUNCH_RESEARCH | BOAMP + TED explicit; large construction market; established paid monitoring/intelligence spend | current explicit binding does not prove complete DECP/national enrichment | LAUNCH_NOW |
| 5 | Italy | BUILD | LAUNCH_RESEARCH | ANAC/BDNCP source contract is rich and market has high account-value potential | localization is regulatory/workflow-heavy; PAD/BDNCP/FVOE/CIG semantics cannot be translated generically | LAUNCH_NOW |
| 6 | Germany | BUILD | LAUNCH_RESEARCH | high-value construction market; official national eForms bulk + TED | daily bulk cadence and German workflow localization increase support/positioning cost | PREPARE |
| 7 | Switzerland | BUILD | LAUNCH_RESEARCH | SIMAP source quality + high ARPU potential | multilingual launch and smaller reachable ICP | PREPARE |
| 8 | Netherlands | BUILD | LAUNCH_RESEARCH | TenderNed + TED, strong official API | smaller market and strong native workflow alternatives | PREPARE |
| 9 | Poland | BUILD | LAUNCH_RESEARCH | large market and BZP source | language/workflow localization + price sensitivity not yet evidenced | PREPARE |
| 10 | United States | BUILD | LAUNCH_RESEARCH | largest WTP upside; SAM federal source proven upstream | federal-only scope, deep incumbents, no SLED completeness | PREPARE |
| 11 | Canada | BUILD | LAUNCH_RESEARCH | CanadaBuys federal source proven; high purchasing power | federal-only; basic alert competition is inexpensive | PREPARE |
| 12 | Colombia | BUILD | LAUNCH_RESEARCH | SECOP/PAA lifecycle + planning signals, shared Socrata reuse | local WTP/channel/support evidence still weak | PREPARE |
| 13 | Brazil | BUILD | UPSTREAM_PENDING | commercial upside remains large | PNCP production live reliability gate | HOLD |
| 14 | Chile | BUILD | UPSTREAM_PENDING | useful official API and attractive marginal engineering economics | real production credential missing | HOLD |

The 31 SHARED countries remain in the registry. TED/eForms countries are researchable only under the explicit TED coverage boundary. Ecuador, Paraguay, South Africa and Uruguay have explicit current shared source bindings. Dominican Republic, Guatemala, Honduras and Peru remain `UPSTREAM_PENDING` in this launch layer until a current explicit shared-source binding can be consumed from upstream; this does **not** demote their upstream SHARED portfolio state.

## Local procurement workflow — first wave

### Portugal

**Observed workflow**

1. Contractor discovers notices/contracts through official procurement publication/search surfaces such as BASE and DRE/TED.
2. Contractor qualifies by contract type, CPV, location, procedure, value, buyer and deadline.
3. The actual procurement procedure may be conducted on a connected electronic procurement platform identified by the notice; BASE is a transparency/contract-information authority, not a universal bid workspace.
4. Bid/no-bid therefore needs a reliable route from intelligence → source notice → procurement platform → internal commercial decision.

**Localization class:** `SEMANTIC_LOCALIZATION` moving toward `WORKFLOW_LOCALIZATION` where procedure/platform routing is exposed.

**Terminology seed:** concurso público; procedimento; empreitada de obras públicas; entidade adjudicante; adjudicatário; preço base; preço contratual; CPV; lote; prazo; peças do procedimento; plataforma eletrónica.

### Spain

**Observed workflow**

1. Companies search PLACSP and can subscribe to daily opportunity updates.
2. Registered users can add an opportunity to `Mis Licitaciones`.
3. Electronic tender preparation/submission is initiated from the selected procurement through the PLACSP tooling where applicable.
4. PLACSP itself warns that email alerts are not legally authoritative; bidders should verify the platform for changes that affect submission.

**Localization class:** `WORKFLOW_LOCALIZATION`.

**Terminology seed:** licitación; órgano de contratación; expediente; pliego; oferta; adjudicación; lote; plazo de presentación; perfil de contratante; Mis Licitaciones.

### United Kingdom

**Observed workflow**

1. Suppliers use the enhanced Find a Tender central digital platform to search notices and save notifications.
2. The Procurement Act 2023 regime exposes lifecycle notice types, including forward-looking pipeline notices, tender notices and contract award notices.
3. Pipeline notices can create materially earlier planning signals than tender-only alerting.
4. Suppliers still follow the notice/document route for participation and tender response; ObraSignal should be a qualification/decision layer, not pretend to replace the procurement platform.

**Localization class:** `REGULATORY_LOCALIZATION`.

**Terminology seed:** pipeline notice; planned procurement notice; preliminary market engagement; tender notice; contract award notice; contracting authority; supplier; lot; framework; dynamic market; SME suitability; bid/no-bid.

### France

**Observed workflow hypothesis requiring customer validation**

1. BOAMP is a core official discovery/alert surface; TED carries EU-threshold notices.
2. Procurement documents/submission can route to buyer profiles/e-procurement platforms named by the notice.
3. Contractors need filtering by geography, lot, trade, procedure, value and deadline, then internal qualification and submission on the designated platform.
4. Current repository binding proves BOAMP + TED, not complete DECP/national enrichment.

**Localization class:** `WORKFLOW_LOCALIZATION`.

**Terminology seed:** marché public; avis; acheteur; pouvoir adjudicateur; accord-cadre; lot; DCE; date limite; candidature; offre; attribution; profil d’acheteur.

### Italy

**Observed workflow**

1. The digital procurement ecosystem uses BDNCP plus certified digital procurement platforms (PAD).
2. Public-contract lifecycle information flows through the national digital ecosystem; CIG is a critical procurement identifier.
3. Economic-operator qualification/evidence intersects with FVOE.
4. ObraSignal must distinguish discovery/intelligence from the certified platform used to conduct procurement actions.

**Localization class:** `REGULATORY_LOCALIZATION`.

**Terminology seed:** stazione appaltante; operatore economico; BDNCP; PAD; FVOE; CIG; bando; gara; affidamento; aggiudicazione; lotto; offerta; DGUE.

## ICP and buyer/user hypotheses — first wave

No ICP below is marked PROVEN until repeated qualified-user evidence exists.

| Country | Initial ICP hypothesis | User | Champion | Buyer/approver | Why this cohort first |
|---|---|---|---|---|---|
| Portugal | 10–100 employee public-works / specialist MEP contractors bidding repeatedly | estimator / commercial technician | commercial manager | managing director / commercial director | reachable, low founder localization burden, visible pain from fragmented discovery + qualification |
| Spain | SME/mid-market construction and specialist contractors with recurring public tender volume | técnico de licitaciones / estimator | responsable de licitaciones | director comercial / gerente | PLACSP discovery is free; value must come from company-specific filtering and decision workflow |
| UK | SME/mid-market contractors with an active bid/preconstruction function | bid manager / estimator / BD | head of bids / preconstruction | commercial director | high value of early pipeline + qualification; strong software WTP category |
| France | SME/mid-market general, civil and specialist contractors regularly monitoring public work | chargé d’affaires / responsable appels d’offres | responsable marchés publics | direction commerciale | paid monitoring category exists; workflow still fragmented across notices and buyer platforms |
| Italy | SME/mid-market public-works contractors with an `ufficio gare` or equivalent | addetto gare / estimator | responsabile ufficio gare | direttore commerciale / amministratore | BDNCP/PAD complexity creates workflow/local terminology value beyond generic alerts |

## Pricing evidence and hypotheses

Pricing remains `HYPOTHESIS`; these are discovery ranges, not authorized price changes or commitments.

| Country | Current market signal | Initial ObraSignal test hypothesis | Main falsifier |
|---|---|---|---|
| Portugal | basic alerting can be ~€8/month; richer tender intelligence products publish prices around ~€110+/month | test value perception around **€79–€149/month** for contractor-specific Radar/decision workflow | qualified contractors treat official/free + cheap alerts as sufficient |
| Spain | official PLACSP is free and several alert aggregators are low-cost; richer intelligence tools are materially higher | test **€99–€199/month** | no measurable time saved / relevance improvement over PLACSP + existing alerts |
| UK | mature intelligence platforms commonly price in the hundreds of pounds per month or thousands/year | test **£199–£399/month** for a construction-specific cohort | ObraSignal lacks enough multi-portal/pre-tender depth to justify premium |
| France | paid monitoring/intelligence subscriptions can reach four figures per year | test **€149–€299/month** | BOAMP/TED-only product is perceived as incomplete vs incumbent coverage |
| Italy | published tender-intelligence plans exist around ~€145–€240/month | test **€149–€249/month** | localization/workflow depth fails to justify parity with incumbents |

Pricing experiments should begin as qualified interviews / landing-page willingness-to-pay tests. Real billing changes remain owned by Revenue/GTM and store-managed regional pricing must not be hardcoded in the mobile app.

## Competitor positioning delta

### Portugal
- Free official sources and very cheap alert products make **“we email tenders” non-differentiated**.
- Positioning candidate: company-specific construction Radar + reasoned relevance + bid/no-bid workflow + source transparency.

### Spain
- PLACSP itself provides search/subscriptions and tender workflow.
- Positioning candidate: reduce qualification noise and commercial review time; never claim to replace PLACSP submission.

### UK
- Incumbents already sell multi-portal aggregation, buyer intelligence, pre-tender signals, award history, AI and team workflows.
- Positioning candidate must be narrower and more defensible: construction-specific contractor fit, explainable relevance and actionability. `AI tender alerts` alone is insufficient.

### France
- Paid tender-monitoring incumbents already have established trust and coverage.
- Positioning depends on proving the exact source/coverage advantage and a faster qualification workflow.

### Italy
- Competitors can price at professional-intelligence levels.
- Native terminology and BDNCP/PAD-aware workflow are table stakes for credibility.

## Channel hypotheses

| Country | HIGH_SIGNAL to test first | TEST | LOW_SIGNAL until evidence |
|---|---|---|---|
| Portugal | targeted founder-led outbound to qualified contractors; LinkedIn; contractor referrals | construction associations/federations; search content around public works opportunities | broad paid ads |
| Spain | targeted outbound to bid-active contractors; LinkedIn | construction federation/association partnerships; procurement consultants | broad paid ads |
| UK | targeted outbound to Bid/Preconstruction leaders; LinkedIn | construction associations; bid consultancies; niche trade media | generic SME advertising |
| France | targeted outbound to appels d’offres/public-works teams | federations; bid consultants; trade media | broad generic search ads |
| Italy | targeted outreach to `ufficio gare` / commercial teams | ANCE/local construction associations; bid consultants | broad paid ads before localization proof |

No mass outreach is authorized by this dossier.

## Soft-launch gate — mandatory per country

A first-wave country may move from `LAUNCH_RESEARCH` only when all of the following have explicit evidence:

1. Upstream source/legal gates still pass at current exact-head/runtime truth.
2. Product coverage claim is precise and does not imply missing national/below-threshold/SLED/provincial scope.
3. Country terminology registry has human/official-source evidence for critical procurement concepts.
4. Local workflow from discovery → qualification → bid/no-bid → official submission route is mapped.
5. At least one ICP cohort and USER/CHAMPION/BUYER map has evidence beyond assumption.
6. Price test hypothesis and success/failure criteria are fixed before collecting results.
7. Local onboarding captures trade categories, regions, contract values, procurement types, keywords and exclusions.
8. Currency/date/time/deadline presentation is verified against local source semantics.
9. A controlled qualified cohort exists; uncontrolled signup volume is not accepted as proof.
10. First value is measured as profile → local Radar → company-specific opportunity → locally sensible reasons/deadline/currency → customer action.
11. Support path exists for launch cohort.
12. No production launch, paid spend or commercial commitment occurs without its owning authorization.

## Active / Next / Wait

**ACTIVE**
- Portugal: terminology + ICP + qualification workflow + pricing interview design.
- Spain: terminology + ICP + PLACSP-to-bid decision workflow + price differentiation test.
- UK: Procurement Act notice taxonomy + early-pipeline value proposition + incumbent gap test.
- France: BOAMP/TED coverage claim audit + buyer-platform workflow + ICP/WTP validation.
- Italy: BDNCP/PAD/FVOE/CIG terminology/workflow + ICP/WTP validation.

**NEXT**
- Build partner candidate registry for these five countries.
- Convert terminology seeds into canonical concept → local term → official source → customer-facing term → internal mapping records.
- Create synthetic country onboarding fixtures and fail-closed localization tests.
- Route pricing hypotheses to Revenue/GTM without committing prices.
- Revalidate Germany, Switzerland, Netherlands, Poland, US, Canada and Colombia after first-wave launch research gaps are structured.

**WAIT**
- Brazil: stable upstream PNCP live production-path proof.
- Chile: real individual Mercado Público production credential.
- Any production soft launch, paid media, contractual partnership or pricing commitment: explicit owner authorization.
