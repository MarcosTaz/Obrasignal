# Country Launch Economics & Partner Discovery v1

Status: **EVIDENCE-BASED PRIORITIZATION — NO COMMERCIAL COMMITMENT**  
Last reviewed: **2026-08-26**

This artifact avoids invented TAM, CAC, conversion and retention percentages. Until ObraSignal has qualified cohort data, launch economics are expressed as evidence states and relative cost/value bands.

## Launch economics comparison

| Country | Engineering increment | Localization/support cost | GTM access | WTP evidence | Competition | Source differentiation | Expected commercial value | Launch decision |
|---|---|---|---|---|---|---|---|---|
| Portugal | LOW | LOW | HIGH | PARTIAL | HIGH at alert layer | MEDIUM if company-specific decisioning works | MEDIUM-HIGH | LAUNCH_NOW |
| Spain | LOW-MEDIUM | MEDIUM | MEDIUM-HIGH | PARTIAL | HIGH | MEDIUM-HIGH from national/sub-threshold workflow + decisioning | HIGH | LAUNCH_NOW |
| United Kingdom | MEDIUM | MEDIUM | HIGH | STRONG CATEGORY SIGNAL | VERY HIGH | MEDIUM; forward pipeline and contractor-specific relevance must outperform incumbents | HIGH | LAUNCH_NOW |
| France | MEDIUM | MEDIUM | MEDIUM | STRONG CATEGORY SIGNAL | HIGH | UNKNOWN until BOAMP/TED vs DECP coverage gap is bounded | HIGH if coverage claim survives audit | LAUNCH_NOW |
| Italy | MEDIUM | HIGH | MEDIUM | PARTIAL-STRONG CATEGORY SIGNAL | HIGH | HIGH potential from BDNCP/PAD-aware workflow, but localization cost is high | HIGH | LAUNCH_NOW |
| Germany | MEDIUM | HIGH | MEDIUM | HYPOTHESIS | HIGH | MEDIUM | HIGH | PREPARE |
| Switzerland | MEDIUM | VERY HIGH multilingual | MEDIUM | HYPOTHESIS | MEDIUM-HIGH | MEDIUM | MEDIUM-HIGH | PREPARE |
| Netherlands | LOW-MEDIUM | MEDIUM | MEDIUM | HYPOTHESIS | HIGH | MEDIUM | MEDIUM | PREPARE |
| Poland | MEDIUM | HIGH | MEDIUM | UNKNOWN | MEDIUM-HIGH | MEDIUM | MEDIUM-HIGH | PREPARE |
| United States | MEDIUM | MEDIUM | HIGH | STRONG CATEGORY SIGNAL | VERY HIGH | LOW-MEDIUM at federal-only scope until a construction-specific edge is proven | VERY HIGH upside / VERY HIGH execution risk | PREPARE |
| Canada | LOW-MEDIUM | MEDIUM-HIGH bilingual | MEDIUM | PARTIAL | MEDIUM-HIGH | LOW at basic federal alerting; decisioning must carry value | MEDIUM-HIGH | PREPARE |
| Colombia | LOW-MEDIUM | MEDIUM | MEDIUM | UNKNOWN | UNKNOWN | HIGH potential from planning + tender lifecycle | MEDIUM-HIGH | PREPARE |
| Brazil | BLOCKED | HIGH | MEDIUM | HYPOTHESIS | HIGH | potentially HIGH via PNCP/PCA planning | UNKNOWN while source gate is blocked | HOLD |
| Chile | BLOCKED ON CREDENTIAL | MEDIUM | MEDIUM | UNKNOWN | UNKNOWN | potentially MEDIUM-HIGH | UNKNOWN while production credential absent | HOLD |

### Interpretation

- **Portugal wins on speed-to-learning**, not theoretical TAM. It is the best place to discover whether contractor-specific Radar and bid/no-bid workflow create enough value above cheap alerts.
- **Spain is the best adjacent replication test**: same EUR billing context but distinct PLACSP workflow and terminology.
- **UK is the strongest premium-positioning test** but also the harshest product-comparison test. Failure there should be classified carefully as coverage/product/positioning/ICP rather than automatically `CHANNEL_GAP`.
- **France has attractive WTP evidence but a source-claim risk**: the commercial dossier must not claim DECP completeness until the upstream binding is proven.
- **Italy has high potential but highest semantic/regulatory localization burden in the first wave**. A translation-only launch would be false localization.
- **US is intentionally not first despite very high upside** because federal-only scope plus deep incumbents creates a high risk of learning the wrong lesson before the core positioning is proven in lower-friction markets.

## Pricing experiment design

Do not change real billing yet. First collect qualified willingness-to-pay signals using the same outcome definition across countries.

For each interview/test capture:

- contractor size and public-tender frequency;
- current discovery stack and monthly/annual spend;
- hours per week spent searching/qualifying;
- number of opportunities reviewed vs pursued;
- job role of USER/CHAMPION/BUYER;
- which ObraSignal output created value;
- stated price reaction at 3 ordered price points;
- whether the respondent would start a 21-day value-aware evaluation;
- exact objection category: coverage, relevance, trust, price, workflow, timing or no pain.

Do not treat stated WTP as revenue proof. `FIRST_REVENUE` requires actual authorized payment; `RETENTION_PROVEN` requires repeat behavior over a defined period.

## Partner discovery — first wave

Partner status below means **candidate**, never agreement or endorsement.

| Country | Candidate | Type | Audience / evidence | Alignment | Initial use | Confidence |
|---|---|---|---|---|---|---|
| Portugal | AICCOPN | national construction association | >6,000 construction/related-sector member companies; provides public-procurement legal support and industry information | HIGH | ICP access, terminology/workflow validation, future education partnership hypothesis | HIGH candidate fit |
| Spain | Confederación Nacional de la Construcción (CNC) | construction confederation | construction-sector representation; publishes on deserted tenders and sector procurement/economic issues | HIGH | ICP interviews, sector pain validation, procurement-content route | MEDIUM-HIGH |
| United Kingdom | Federation of Master Builders (FMB) | SME builder federation | publishes direct guidance on how SME builders find/win public-sector work and bid/no-bid considerations | VERY HIGH for SME cohort | ICP recruitment and pain/workflow validation | HIGH |
| United Kingdom | Civil Engineering Contractors Association (CECA) | civil engineering contractor association | 300+ firms; active procurement reform/framework work | HIGH for infrastructure cohort | mid-market/infrastructure ICP and procurement workflow validation | HIGH |
| France | Fédération Nationale des Travaux Publics (FNTP) | public-works federation | ~8,000 TP companies; current legal/procurement resources and buyer-specific market rules | VERY HIGH | ICP access, terminology, buyer/workflow segmentation | HIGH |
| Italy | ANCE | national construction association | dedicated public-works/legal function; current operational material on public-procurement code, ANAC and below-threshold procedures | VERY HIGH | ICP access, regulatory terminology/workflow validation | HIGH |

## Partner qualification gate

Before any outreach or partnership claim, record:

1. exact target audience overlap with the selected ICP;
2. evidence that procurement/opportunity discovery is a live member pain;
3. a low-friction value exchange (research interview, educational session, member pilot, integration, referral or content);
4. commercial model only after proof of value;
5. no logo, endorsement, testimonial or `partner` language without actual agreement;
6. owner authorization before contractual or paid commitment.

## Channel experiment order

1. **Qualified direct discovery** — 10–20 highly selected companies per country, but no mass outreach; any sending remains authorization-bound.
2. **Role-specific LinkedIn discovery** — Bid Manager / Estimator / Commercial / Preconstruction / Ufficio Gare / Responsable Licitaciones roles.
3. **Association-led validation** — use candidate bodies above to test terminology, pain and cohort access, not to claim partnership.
4. **Consultant channel** — bid-writing/procurement consultants can validate repeated pain across many firms.
5. **SEO/content** only after terminology and source-coverage claims are country-correct.
6. **Paid acquisition** remains blocked until first-value and conversion evidence exists.

## Reopen / demotion logic

- If a top-five market cannot produce repeated pain or WTP evidence after a qualified cohort, demote `LAUNCH_NOW → PREPARE/HOLD` and classify the failure.
- If source/legal truth regresses, immediately demote the affected country to `UPSTREAM_PENDING`, regardless of commercial traction.
- If a cheap/free incumbent is sufficient for the target ICP, change the ICP/value proposition before lowering price reflexively.
- If users value ObraSignal but do not pay, investigate buyer/approver and packaging before calling it product-market fit.
