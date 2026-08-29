# RoyaltyRecover — Forensic Validation

Status: THESIS SURVIVES, GENERIC WEDGE NOT YET UNIQUE
Date: 2026-08-29
Base repository: MarcosTaz/Obrasignal
Branch: royaltyrecover/company-web-app
Base main SHA: 66d43f6fd51cf9cea08016dad335aaa04b711a24

## Evidence-backed problem

- University of California's systemwide royalty audit program (FY10-FY16) completed 27 audits; 16 identified underreported royalties. UC reported >$3m identified, $1,634,140 recovered in 13 audits, $655,910 professional fees, $220,550 audit fees recovered from licensees, and 275% ROI; two separate campus settlements totalled $16,101,508. Source: https://www.ucop.edu/ethics-compliance-audit-services/_files/compliance/education/context-sheets/royalty-audit-program.pdf
- Vianix v. Nuance records an Invotex audit finding of $2,488,218 underpayment ($2,009,604 royalties + $478,614 interest), excluding additional periods/products. Source: https://law.justia.com/cases/delaware/court-of-chancery/2010/142180-1.html
- InvotexIP states it has performed hundreds of royalty compliance examinations and clients recovered >$400m based on its audits; a recent-results case reports an approximately $2m underpayment paid after omitted sales/territories were found. Sources: https://www.invotexip.com/services-test and https://www.invotexip.com/recent-results
- Adeptus states its royalty/contract-compliance team has recovered hundreds of millions for clients. Source: https://adeptusadvisors.com/what-we-do/audit-reviews-compilations/royalty-audit/
- CRA documents a biotech audit where products made with licensed protein-growth technology and research products had been omitted from royalty calculations. Source: https://www.crai.com/engagements/royalty-audit-concerning-use-licensed-technology/

## Audit-right structure is real and economically useful

Publicly filed licensing agreements repeatedly require complete records, permit periodic independent audits, commonly cap lookback to ~3 years, and often shift audit cost to the licensee when underpayment exceeds 5% (sometimes 10%). Examples:
- https://www.sec.gov/Archives/edgar/data/1808945/000119312520252416/d903272dex1010.htm
- https://www.sec.gov/Archives/edgar/data/1690437/000138713117004440/ex10-4.htm
- https://www.sec.gov/Archives/edgar/data/821995/000082199511000032/exhibit102actientlicenseag.htm
- https://www.sec.gov/Archives/edgar/data/1819411/000114036121005495/nt10015006x7_ex10-3.htm

Important product consequence: audit rights, lookback, frequency, auditor qualification, confidentiality, fee shifting, interest and closure language must be contract-specific fields. Never infer them from market norms.

## Serious competition

### Audit / compliance firms
- InvotexIP — patent royalty audits, technology transfer, hundreds of examinations, recovery support.
- Stout — desk/field audits, royalty compliance and monitoring programs across technology, life sciences, automotive, electronics and other sectors.
- Adeptus — royalty and contract compliance, recovery, due diligence, audit defense.
- CRA — royalty audits with technical experts and life-science/technology capability.
- 360 Forensic — global royalty audits, proprietary software/data solutions, fixed or contingent fees.
- Connor Consulting — end-to-end pharma royalty oversight including contract review, risk analysis, royalty audit, data reconciliation, patent-attorney/legal expertise and compliance-program design.
- RMA / ILS Rights / EisnerAmper / HW Fisher and others provide recurring audit programmes and/or royalty recovery services.

### Software / technology overlap
- FADEL IPM Suite / LicenSee — contract terms, automated royalty calculation, sales/usage processing, validation, statements, compliance checks, audit trails and audit readiness.
- IMA360 — royalty management plus continuous transaction-vs-contract compliance monitoring, exception workflows and evidence/audit trails.
- Dependable Solutions / Mediabox / RoyaltyCentral and others support royalty validation, contract/rate management and auditability.
- Quartiq is the most direct threat found so far: licensor-focused continuous compliance monitoring, 60+ checks, near-real-time flags, 100% portfolio coverage, audit augmentation, expert oversight and SaaS used by royalty audit firms. Source: https://quartiqcompliance.com/

## Differentiation conclusion

The original generic claim — automated royalty leakage detection + continuous monitoring — is NOT sufficiently differentiated. Existing software and Quartiq directly occupy much of that territory.

The surviving wedge must be narrower and recovery-centric:

**INDEPENDENT PATENT / TECHNOLOGY ROYALTY RECOVERABILITY ASSURANCE**

1. No rip-and-replace: operate from agreements, amendments, statements, payments and exported source data.
2. Statement-first portfolio triage before expensive field audit.
3. Explicit evidence lineage from clause -> rule -> source records -> deterministic calculation -> variance.
4. Fail-closed finding states: UNKNOWN / NEEDS DATA / REQUIRES PROFESSIONAL REVIEW / NO DEFENSIBLE RECOVERY / RECOVERY CANDIDATE.
5. Contract-specific audit-right and deadline extraction, with no invented rights.
6. Auditor-ready evidence packs and data requests rather than pretending software alone can compel access to licensee books.
7. Partner-compatible formal audits when agreement language requires an independent CPA/accountant/qualified auditor.
8. Recovery ledger through settlement/payment, so success is actual incremental money received, not anomaly count.

## Initial vertical ranking

1. Patent / technology licensing — strongest initial wedge. High audit-right prevalence in university/technology licensing, strong quantified recovery evidence, technical product-classification leakage, multiple-licensee portfolios, large economic density.
2. Life sciences / biotech licensing — extremely high value and audit-right prevalence, but higher legal/technical complexity and longer sales cycle; strong second vertical or specialist lane.
3. Industrial / OEM embedded technology — attractive value density and classification/territory/sublicense leakage; evidence still needs deeper quantified validation.
4. Brand / character licensing — large market and strong auditability, but heavier software/audit competition.
5. Franchising — frequent reporting and clear data, but crowded and can involve franchise-law complexity; not first wedge.
6. Entertainment/music — proven recoveries but highly specialized incumbents and fragmented data ecosystems; not first wedge.

## ICP hypothesis now

Primary: licensors with multiple patent/technology licensees and annual royalty income >= $1m equivalent, especially university/research TTOs, corporate technology licensors and IP-holding businesses where audit rights exist and no continuous independent verification is in place.

Secondary: life-science licensors with meaningful commercialization-stage royalties and/or sublicense revenue.

The prior >= €250k threshold remains testable for a low-cost scan, but the full-audit economic sweet spot likely starts materially higher.

## Commercial offer modification

Do not initially sell 'royalty management software'.

Sell:

**ROYALTY RECOVERABILITY SCAN — WHICH LICENSEES ARE WORTH AUDITING BEFORE THE LOOKBACK WINDOW CLOSES?**

Inputs: agreement + amendments + statements + payments + available sales/usage exports.

Outputs per licensee:
- audit-right status and constraints;
- data sufficiency;
- deterministic statement/payment recomputation;
- anomaly / rule-breach candidates;
- potential value range only where supported;
- missing evidence and information request;
- deadline / lookback risk;
- formal-audit recommendation;
- evidence pack for qualified auditor/counsel.

Formal field audit and recovery support follow only where contract/data/professional boundaries permit.

## Current score /100

Problem severity: 10/10
Recoverable value: 9/10
Audit-right availability: 9/10 for selected patent/technology wedge
Data access before formal audit: 5/10
Competition: 5/10
Differentiation after narrowing: 7/10
Gross-margin potential: 8/10
Sales-cycle attractiveness: 6/10
International scalability: 8/10
Legal/professional defensibility: 7/10 with partner boundary

**Initial weighted thesis score: 79/100 — PROCEED, MODIFIED WEDGE.**

This is not Gate 3 freeze yet. Remaining P0 validation: exact professional/legal boundary by launch jurisdiction, competitor teardown of Quartiq/Connor/FADEL/IMA360, pricing evidence, and synthetic recoverability scan proving the narrow wedge can avoid false claims.
