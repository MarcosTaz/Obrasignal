# RoyaltyRecover — Legal & Professional Boundary

Date: 2026-08-29
Status: INITIAL BOUNDARY, JURISDICTION REVIEW REQUIRED BEFORE REAL CLAIM/REPRESENTATION

## Operating rule

RoyaltyRecover may perform documented data reconciliation, deterministic arithmetic, evidence lineage, contract-reference extraction and workflow support. It must not silently convert those functions into legal advice, regulated accounting opinions, formal audit work reserved/required by agreement, or representation in a dispute.

Every output must be classed as one of:

- DOCUMENTED_FACT
- DATA_RECONCILIATION
- MATHEMATICAL_CALCULATION
- CONTRACTUAL_REFERENCE
- ANALYTICAL_FINDING
- LEGAL_INTERPRETATION_REQUIRED
- ACCOUNTING_JUDGMENT_REQUIRED
- QUALIFIED_AUDITOR_REQUIRED

The last three never become an automated money claim.

## Contract-specific audit rights

Audit rights are contractual, not assumed. Public licensing agreements demonstrate that requirements vary materially: independent CPA/qualified auditor requirements, audit frequency, notice, confidentiality, lookback periods, cost shifting and interest are negotiated fields. RoyaltyRecover therefore stores these as sourced facts from the operative agreement/version. Missing or ambiguous language => UNKNOWN / PROFESSIONAL_REVIEW.

Example public agreement source: https://www.sec.gov/Archives/edgar/data/1070494/000156459019004596/acad-ex1026_573.htm

## Formal auditor boundary

Where an agreement requires an independent CPA, certified accountant, qualified auditor, nationally recognized firm or similarly specified professional, RoyaltyRecover's software analysis does not satisfy that contractual appointment requirement unless the appointed provider independently meets it.

The product may prepare a desk-review/evidence pack for that professional, ingest the professional result, and track recovery. It must not label an internal scan a "formal contractual audit" unless the applicable agreement and professional requirements are actually satisfied.

## Portugal lawyer-fee boundary

Portugal's Estatuto da Ordem dos Advogados, Article 106, prohibits a lawyer from a pure quota-litis arrangement where entitlement to fees depends exclusively on the result and the client pays a share of that result. Article 106(3) provides exceptions for a pre-agreed amount based on the value of the matter and for a success uplift added to fees calculated using other criteria. Article 107 restricts lawyers' sharing of legal fees except in specified professional/multidisciplinary settings.

Official sources:
- https://portal.oa.pt/ordem/regras-profissionais/estatuto-da-ordem-dos-advogados/
- https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-105332944-105333056

Consequences:
1. Do not assume RoyaltyRecover can fund or share a lawyer's pure percentage-of-recovery fee.
2. Keep legal-adviser engagement and fee compliance independently structured.
3. Do not describe RoyaltyRecover's proposed 10–25% success component as legally validated in Portugal merely because non-legal audit firms elsewhere use contingent pricing.
4. Before launch, obtain jurisdiction-specific advice on RoyaltyRecover's own success-fee model, debt-collection/claims-handling boundaries, tax/VAT treatment and any professional-services characterization.

## Recovery workflow boundary

Allowed without claiming legal status:
- produce transaction/calculation schedules;
- list sourced discrepancies;
- generate factual information requests for human approval;
- calculate supported arithmetic differences;
- track response, settlement and payment evidence;
- route items to counsel/auditor.

Requires qualified/professional review when applicable:
- decide disputed contract meaning;
- assert breach as a legal conclusion;
- waive rights or limitation defenses;
- threaten or commence proceedings;
- negotiate/settle on behalf of a client where representation rules apply;
- issue an auditor opinion/certification reserved by contract or law.

## Pricing status

Commercial evidence supports fixed-fee and contingent royalty-audit arrangements in some markets, but RoyaltyRecover's exact success-fee legality is NOT_YET_VERIFIED by launch jurisdiction. Until verified, product pricing architecture must support fixed fee + subscription independently of a contingent component.

## Gate consequence

GATE 4 — LEGAL BOUNDARY DEFENSIBLE: PARTIAL / NOT PASSED.

Pass requires a launch-jurisdiction checklist covering Portugal/EU initial operations and the intended customer jurisdictions, plus explicit partner engagement rules for formal auditors and lawyers.
