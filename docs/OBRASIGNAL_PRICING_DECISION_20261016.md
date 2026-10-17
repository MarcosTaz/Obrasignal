# OBRASIGNAL — Price architecture / decision record (proposed; not published)
Date: 2026-10-16. Market references checked against public vendor pricing.
**Not an instruction to create Stripe/RevenueCat products or charge any customer.**
All amounts are **EUR/month, excluding VAT**, billed monthly, and remain **proposals** pending feature evidence and acceptance.

## Competitive anchors (published public vendor pages)
- Alerta Concursos Públicos: €10/month, or €8/month equivalent annually; primarily monitoring and email alerts. https://alertaconcursospublicos.pt/precos/
- TenderWolf: Free, Standard €79/month (€790/year), Professional €149/month (€1,490/year). Its policy lists all features available across plans but credit/coverage differences. https://www.tenderwolf.com/en/help-center/tenderwolf-pricing/
- TenderLens: Intel €149/month, Pro €299/month (early access), with features advertised subject to verification. https://tenderlens.app/
- TenderEU: single-country Search €200/month; multi-country €600/month; filling €3,000/month. https://www.tendereu.ai/pricing
- Tenderlake Monitor: UK/IE £325/month monthly, Europe/UK/Int+ £546/month monthly; annual equivalents lower. Different seats/coverage and currency. https://www.tenderlake.com/pricing/index

## Proposed price table / milestone gates
| Plan | Proposed monthly price (ex VAT) | Buyer | Entitlement justified by evidence |
|---|---:|---|---|
| **Radar** | **€89** | Small specialist bidder focused on one market | Verified tender sourcing; 1 company profile; ranking/why match; deadlines and original links; 2 seats; core alerts ONLY after end-to-end delivery proof |
| **Decisão** | **€229** | Bid team selecting tenders consistently | Radar + five seats + evidence gaps/eligibility flags/UNKNOWN queue, traceable reasons and qualification decisions, exports ONLY after tests |
| **Controlo** | **€549** | Multi-team/multi-market pursuit operation | Decisão + 15 seats + approval workflow, change and deadline accountability, dossiers, reporting, multilingual coverage ONLY for actually proven markets |
| **Enterprise** | **Custom** | Complex procurement team | Commercial scope, SLA, integrations, API and data governance individually verified before sale |

**No plan should be sold based on a feature claim that the current production build cannot pass in an end-to-end test.** The highest plan is not automatically better: it needs economically proven value.

## Why these numbers, not inherited €249/€499/€999
€249 starts above TenderWolf Standard and Professional and TenderLens Intel, before the product has yet demonstrated its full competitive advantage. Launching at €249 as the bottom tier is too demanding for unproven market fit. The proposed €89 lowers initial adoption friction while keeping the offer positioned above €10 plain monitoring. €229 is supported only by verified decisions and evidence workflows; €549 only by verified team/multi-market capabilities. Differentiation = **Source truth → Eligibility → Fit → Readiness → Economics → Decision/Buy**, not invented AI claims.

## Price mechanics
- Display VAT treatment explicitly; do not silently claim tax included.
- Do not invent customer ROI, conversion, procurement win probability, or guaranteed revenue.
- A trial or assisted pilot can be offered only with its exact terms visible; no automatic recurring subscription without a configured and proven checkout.
- For annual billing consider **10 months charged for 12 months' access**, applied consistently: Radar €890/year, Decisão €2,290/year, Controlo €5,490/year, only after confirming gross margin and billing support. These are hypothetical annual options, NOT active prices.
- Avoid unlimited costly AI/translation/API usage until compute and provider budgets are observed. Maintain a transparent fair-use policy for variable cost drivers.
- Seats are a commercial proposal, not technically enforced limits; verify authorization and counting before publishing.
- Profitability per plan: gross margin = revenue (excluding VAT) - recurring infrastructure - transactional email - AI/translation - per-customer support - payment fees. Require real measurements before launch.
- Existing backend currently recognizes evaluation/pro/pilot/expired with **one** RevenueCat entitlement `pro` and one product `obrasignal_pro_monthly`. No tiering exists in the tested billing contract. Do NOT represent the 3-tier table as implemented.
- Existing billing identity = Supabase user ID; a switch to Neon Auth must preserve entitlement identity mapping; otherwise payment entitlement can be lost.

## Release gates
1. Auth migration and invited registration proven end-to-end; no existing customer cut off.
2. All marketed capabilities individually proved from source → decision → report/export; UNKNOWN accurately displayed.
3. Implement three separate server-authoritative subscription plans, seat limits and downgrade semantics; signed webhook replay/idempotence + refund/cancel/expiry cases.
4. Approve actual legal merchant and billing configuration, with user's explicit authorization before any paid service/payment.
5. Publish exact product features and prices, VAT and recurring terms only when proved.
