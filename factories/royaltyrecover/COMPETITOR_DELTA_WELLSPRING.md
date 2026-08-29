# RoyaltyRecover — Competitor Delta: Wellspring / TTO Internal Automation

Date: 2026-08-29
Status: MATERIAL DIFFERENTIATION CHALLENGE

## New evidence

University of Colorado's FY25 internal-audit-plan material describes a CU Boulder Royalty/Licensing Fee Receivables review. It states that Internal Audit would evaluate the development of an **automated rubric applied against information in the new Wellspring system to flag license agreements that may be out of compliance**.

Source:
- https://www.cu.edu/doc/3d-fy25-internal-audit-planpdf

This is direct evidence that a sophisticated TTO can build risk/compliance flagging on top of its incumbent technology-transfer system. Therefore:

**"Automated portfolio risk scoring" is not a sufficient RoyaltyRecover wedge.**

Wellspring's own current product/service pages strengthen the collision:
- Evolve positions itself as an end-to-end TTO platform covering financial management and contract compliance;
- its Partner Portal tracks financial obligations, payment deadlines and royalty calculations;
- its Data & Operations service offers agreement entry/audits, financial-term management, reconciliations and finance operations;
- Wellspring says hundreds of institutions rely on its technology-transfer systems.

Sources:
- https://www.wellspring.com/technology-transfer
- https://www.wellspring.com/evolve
- https://www.wellspring.com/data-and-operations-support

A UC Regents review also states that UC San Diego and UC Riverside had implemented Wellspring, while UCLA and UC Davis had implemented Inteum. This shows that the beachhead includes institutions with incumbent TTO systems rather than spreadsheet-only operations.

Source:
- https://regents.universityofcalifornia.edu/regmeet/sept22/s4attach.pdf

## Surviving wedge

RoyaltyRecover must be independent of the incumbent TTO system and useful **without migration**.

The surviving job is narrower:

`INDEPENDENT CONTRACT-TO-CASH ROYALTY RECONCILIATION + RECOVERABILITY LINEAGE`

not:

`TTO management software`

and not:

`royalty compliance risk score`.

Required differentiation:
1. consume exports/evidence from Wellspring/Inteum/spreadsheets/accounting rather than replace them;
2. bind every monetary candidate to the operative agreement version, reviewed source clause/rule, calculation engine version, input hash and evidence hashes;
3. invalidate stale calculations when contract/data/engine changes;
4. preserve clean/no-recovery outcomes and evidence gaps instead of optimizing for flags;
5. keep analytical candidates distinct from legal claims/formal audit conclusions;
6. create auditor-ready handoff packets without pretending to replace a contract-required independent auditor;
7. reconcile the external audit/settlement/payment outcome back to `VERIFIED_PAYMENT`;
8. make portfolio baseline economics materially cheaper than license-by-license desk-audit work.

## Competitive consequence

A TTO that already has Wellspring can still be a buyer only if RoyaltyRecover can prove that it provides **independent assurance over the economics represented in the system**, rather than another view of the same operational data.

That creates a useful independence narrative:

`SYSTEM OF RECORD / OPERATIONS PLATFORM`
+
`INDEPENDENT RECONCILIATION / ASSURANCE LAYER`

But this narrative remains a hypothesis until a buyer or auditor validates it.

## Gate impact

- Gate 2 beachhead remains PASS: the need/problem still exists in sophisticated TTOs.
- Gate 3 remains OPEN and the burden of proof increases.
- Any positioning centered on automated risk ranking is retired.
- Product work should prioritize import adapters, deterministic evidence lineage, outcome truth and no-migration operation over generic scoring features.

## Next product implication

Build a canonical import boundary that accepts normalized records from external TTO/finance systems while preserving source-system identifiers and evidence hashes. Do not create a Wellspring-specific integration until there is buyer evidence that API/file access is available and commercially useful.
