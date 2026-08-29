# RoyaltyRecover — Wedge Decision 02

Date: 2026-08-29
Status: MODIFIED / GATE 3 STILL OPEN

## New collision

Deadline/lookback tracking is not unique by itself.

- Tallowe tracks royalty audit-clause deadlines, lookback periods, variances and evidence packs, but explicitly states that it performs no automatic imports, determines no underpayment and performs no audit. Its target is books/games rather than high-value B2B patent/technology portfolios.
- General IP/contract tools such as Contracko track audit rights and reporting/renewal deadlines and extract royalty terms.
- Royalty Reporting publishes lookback/exposure tooling from the licensee reporting/compliance side.

Sources:
- https://apps.apple.com/sr/app/tallowe/id6784563256
- https://contracko.com/industries/intellectual-property
- https://royalty-reporting.com/resources/glossary/audit-lookback-period
- https://royalty-reporting.com/resources/calculators/audit-exposure-estimator

## Surviving compound wedge

**ZERO-MIGRATION RECOVERABILITY TRIAGE FOR B2B RUNNING-ROYALTY PORTFOLIOS**

Not a reminder product. Not a royalty-management replacement. Not a formal audit firm.

The entry product must combine, in one defensible workflow:

1. ingest operative agreement + amendments;
2. identify sourced audit-right/lookback constraints;
3. ingest statements + payments + available transaction/usage exports;
4. deterministically recompute what can be recomputed;
5. explicitly fail closed on ambiguity/incomplete evidence;
6. rank licensees by supported value + deadline risk + evidence readiness;
7. generate the exact missing-data request and auditor-ready evidence packet;
8. route formal audit where contract/professional requirements demand it;
9. track recovery to verified incremental cash.

A deadline alert without reconciliation is commodity. Reconciliation without recoverability/deadline routing collides with enterprise royalty software and audit firms. The product hypothesis is the low-friction bridge between passive statements and the decision to spend money on a formal audit.

## ICP refinement

Initial commercial focus remains a hypothesis:
- B2B licensors with running royalties rather than lump-sum-only deals;
- multiple licensees but no dedicated large compliance operation;
- patent, technology, industrial/OEM and selected life-science agreements;
- enough royalty density that a missed audit window is economically material.

Do not yet hard-code 3–30 licensees or EUR 1m–25m royalty income into product qualification. Those are test bands, not validated market cutoffs.

## Positioning candidate

**"Before you commission another royalty audit, know which licensees are actually worth auditing — and which contractual windows are closing."**

Supporting proof must be the contract, source data and deterministic calculation. If those are missing, output NEEDS_DATA / PROFESSIONAL_REVIEW rather than a recovery number.

## Gate consequence

Gate 3 remains OPEN because Connor already provides data-driven desk reviews and tiered compliance programs. The remaining differentiation test is economic/deployment: can RoyaltyRecover deliver this zero-migration portfolio triage materially faster/cheaper and distribute through auditors/IP advisers without competing with them?
