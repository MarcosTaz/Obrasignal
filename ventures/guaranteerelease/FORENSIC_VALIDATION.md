# GuaranteeRelease — Forensic Validation

Date: 2026-08-29
State: NARROW → PROMOTE SURVIVING WEDGE

## Executive decision

The broad thesis "software to manage bank guarantees / bonds" is rejected as insufficiently differentiated.

The surviving company is narrower:

**CONTRACTOR-SIDE RELEASE & REDUCTION RECOVERABILITY ASSURANCE**

Independent of the customer's existing TMS/ERP/bank/surety portal, GuaranteeRelease reconstructs the contractual security lifecycle, reconciles project evidence against each instrument, identifies reductions/releases that may now be supported, creates an evidence-backed action queue, and verifies the downstream economic result.

This is not an issuer, broker, lender, surety, TMS, CLM or generic guarantee register.

## Why the thesis survives

### 1. Material exposure is proven

Ferrovial disclosed EUR 8.548bn of bank guarantees and insurance/surety guarantees at 30 June 2025, including EUR 2.599bn of bank guarantees and EUR 5.949bn of guarantees issued by bonding agencies and insurers. These guarantees largely cover performance of construction and service contracts.

Source: https://financialfilings.com/filings/ferrovial/interim-quarterly-report/2025/7629174/

Dovre Group disclosed approximately EUR 28.8m of financial-institution guarantees tied to construction/warranty periods and additionally pledged EUR 5.4m of account funds as collateral for bank guarantees after the reporting period.

Source: https://kommunikasjon.ntb.no/pressemelding/18508910/dovre-group-trading-statement-january-1-march-31-2025?lang=en&publisherId=4954260

Conclusion: security portfolios can consume economically material guarantee lines, surety capacity and cash collateral.

### 2. Release/reduction is contract- and evidence-dependent

FIDIC states that an advance-payment guarantee is linked to the advance payment and its amount should reduce in step with repayment. FIDIC also warns that delaying release of bonds can create economic difficulty and loss.

Source: https://fidic.org/node/760

Construction disputes confirm that return/release may depend on practical completion, final certificates, defect periods, deeds of release and other evidence rather than a simple expiry date. In Synergy Construct Australia v GSA North Terrace, three bank guarantees of just under AUD 2m were tied to milestone-based release obligations.

Source: https://www.hsfkramer.com/notes/construction/2026-posts/a-blow-to-the-reputation-of-unconditional-bank-guarantees

Conclusion: an instrument register alone is not enough to determine recoverability.

### 3. Capacity is commercially consequential

Industry evidence shows that surety/bond capacity can constrain new project starts and bidding. UK construction reporting in 2024–2026 described a shortage of bond capacity and specifically identified reluctance to release bonds early as a contributor.

Sources:
- https://www.constructionenquirer.com/2024/06/21/early-bond-release-key-to-averting-industry-surety-crisis/
- https://www.clarionsolicitors.com/articles/bonds-and-guarantees-what-are-they-and-why-do-we-need-them

Conclusion: restored capacity can have real strategic value even when it is not liquid cash.

### 4. Manual/fragmented administration remains real

Arup publicly described moving from Excel-based guarantee application, maintenance and reporting to specialized automation.

Source: https://treasury-management.com/articles/goodbye-excel-automating-bank-guarantees-at-arup

Guarantee Vault reports that managing outstanding guarantees across multiple banking and surety partners has been a significant challenge for market participants.

Source: https://www.assurodigitalservices.com/services/beneficiary

Conclusion: fragmented source systems and cross-functional ownership are plausible root causes for missed or late release action.

## Kill-test result

### Proven

- Large contractors can carry very large guarantee/surety portfolios.
- Guarantees can consume facility capacity, bonding capacity and collateral.
- Some guarantee types are explicitly reducible as underlying exposure falls.
- Release may require project/contract evidence and beneficiary action.
- Bonds/guarantees may remain active until formal release documentation is produced.
- Delayed release can continue premium/fee burden and capacity consumption.
- Existing enterprise and specialist software already covers much of the lifecycle/register/workflow problem.

### Signal

- A meaningful subset of portfolios likely contains stale, over-sized, administratively stranded or insufficiently chased instruments.
- Contractor-side independent recoverability analysis may be valuable where treasury systems know the instrument but not enough project/contract truth to determine what should happen next.
- A historical cleanup audit can create a credible entry point before recurring monitoring.

### Unknown

- Typical percentage of an enterprise portfolio that is actually reducible/releasable earlier than current treatment.
- Median time from contractual release condition to verified bank/surety cancellation.
- Buyer willingness to pay for independent recovery assurance rather than internal process improvement.
- Real conversion rate from identified candidate to verified capacity/cash/fee outcome.

These unknowns must be tested commercially; they are not fabricated as solved.

## Competition — hard correction

The generic product is crowded.

### Direct / near-direct lifecycle platforms

- SAP S/4HANA Treasury & Risk Management: bank guarantee lifecycle, fee calculation, facilities, termination/settlement.
  https://help.sap.com/docs/SAP_S4HANA_CLOUD/e5ec5859d8e54df98492d80564a734c0/53880d5791c45d38e10000000a44147b.html
- Finelia Guarantee: entire guarantee/SBLC lifecycle through final release, facility utilisation, financial expenses and alerts.
  https://www.finelia-software.com/en/products/finelia-guarantee/
- Surecomp RIVO: release and reduction workflows, including 2026 reduction support for incoming guarantees/outgoing standby LCs.
  https://rivo-support.surecomp.com/hc/en-us/articles/49560479633681-Release-Notes-Ver-4-6-Aug-05-2026
- Guarantee Vault: issuance, post-issuance amendments/releases/claims, multi-guarantor connectivity.
  https://www.assurodigitalservices.com/how-it-works
- bondtrack: contractor-focused bond/bank-guarantee lifecycle, late-return costs, automated reconciliation and released capacity.
  https://bondtrack.app/

### Consequence

GuaranteeRelease must **not** compete as another system of record or workflow portal.

It must enter as an **independent recoverability layer** that can sit above exports from these systems and answer a different question:

> Based on the actual contract, amendments, payment certificates, milestones, defects status and instrument wording, what security is still economically/contractually justified; what may now be reducible or releasable; what evidence is missing; and what outcome was actually verified?

## Frozen wedge

### Initial industry

**Construction / EPC / infrastructure contractors** with multi-project portfolios and recurring outgoing performance, advance-payment, retention/warranty guarantees or surety bonds.

### Initial ICP

Prioritize contractors that have:

- >= 20 live security instruments OR >= EUR 10m equivalent outstanding security exposure;
- at least 2 banks/sureties or multiple facilities;
- active pipeline where guarantee/bond capacity matters;
- contracts with milestone, practical-completion, advance-repayment, defects/warranty or final-certificate triggers;
- accessible contract, instrument and project evidence;
- treasury/commercial/project ownership split across teams.

Thresholds are working qualification hypotheses, not proven market standards.

### Primary instrument wedge

1. **Advance Payment Guarantees** — strongest deterministic reduction logic because exposure can fall as certified repayment occurs.
2. **Performance Guarantees/Bonds** — material, often tied to practical completion/final certificate and project closeout.
3. **Retention / Warranty / Defects Guarantees** — strong release-event logic but longer time horizon.

Bid bonds and unrelated financial guarantees are secondary until evidence shows equal or better economics.

## Buyer map

Economic buyer candidates:

- CFO / Finance Director
- Group Treasurer / Treasury Manager
- Commercial Director

Operational users:

- Treasury analyst / guarantee administrator
- Commercial/contracts manager
- Project controls / project director
- Legal/contracts reviewer

A sale is strongest where treasury owns facility pressure but commercial/project teams own the evidence required to release it.

## Verifiable outcome hierarchy

Never collapse candidate value into verified value.

1. Potential reduction identified
2. Evidence-supported reduction candidate
3. Reduction request sent
4. Beneficiary-approved reduction
5. Bank/surety implemented reduction
6. Facility/bonding capacity restored
7. Cash collateral actually released
8. Avoided future fees supported by bank pricing/time evidence
9. Revenue charged by GuaranteeRelease

## Commercial model — first hypothesis

Do not rely on a pure percentage of nominal security as if it were cash recovered.

Test a hybrid:

- fixed historical portfolio audit fee;
- fixed per-instrument success fee for verified bank/surety reduction/cancellation;
- percentage success fee only where liquid cash collateral or directly measurable bank/surety fees are actually released/avoided;
- recurring monitoring subscription after cleanup.

Exact pricing remains ASSUMPTION until market evidence exists.

## Near-zero-capital test

PASS for assisted delivery.

Required initial resources are document ingestion, structured reconciliation, analyst review, evidence packaging and workflow tracking. GuaranteeRelease does not lend, issue guarantees, underwrite surety, hold collateral or take balance-sheet risk.

## Distinctness from portfolio companies

- ObraSignal: opportunity/procurement intelligence.
- ScopeLedger: change/time/entitlement protection.
- EarnedCash: money earned but not received.
- Industrial Claims: complex industrial disputes/recovery.
- GuaranteeRelease: financial-security lifecycle → independent release/reduction recoverability → verified capacity/collateral/fee outcome.

Cross-referral is preferable to horizontal scope creep.

## Current classification

THESIS_STATE = NARROW_PROMOTED
DISTINCTNESS_STATE = SURVIVES_WITH_NARROW_WEDGE
ICP_STATE = DEFINED_HYPOTHESIS
BUYER_STATE = DEFINED_HYPOTHESIS
MATERIALITY_STATE = PROVEN
COMPETITION_STATE = STRONG_AND_CROWDED_GENERIC_LAYER
WTP_STATE = UNPROVEN

CURRENT_WEDGE = Contractor-side independent release/reduction recoverability assurance for construction/EPC security portfolios.

ONE_CURRENT_BOTTLENECK = Prove that real portfolios contain enough actionable excess/stale security to justify paid audits.

SHORTEST_TEST = Run a controlled historical portfolio audit against synthetic oracle cases now; then expose the same workflow to real anonymized/exported customer data when available.
