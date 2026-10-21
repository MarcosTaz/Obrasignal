# RoyaltyRecover — Repeatable Recoverability Method v0.1

Date: 2026-08-29
Status: IMPLEMENTED IN PART / SYNTHETICALLY TESTED IN PART

## Purpose

Define the repeatable operation for deciding whether a running-royalty licensee should be closed, investigated further, desk-reviewed, or routed to a qualified formal auditor.

## Method

1. **Portfolio intake** — register licensor, licensee, agreement, known versions/amendments, statements, payments, available source data, annual stream, audit history and sourced audit/lookback fields. Missing remains UNKNOWN.
2. **Freeze operative contract set** — hash every known agreement version, capture effective dates, and block positive conclusions when the operative version is incomplete or unresolved.
3. **Extract sourced economic rules only** — every rate/base/tier/deduction rule links to the operative source clause. Unsupported mechanics route to professional review.
4. **Separate audit rights from economics** — audit right, notice, lookback, auditor qualification, reimbursement and interest are independent sourced fields. Arithmetic does not create contractual rights.
5. **Normalize evidence** — statement, payment, sales/usage data, deduction support, FX source/date and relevant product/territory/channel mappings retain lineage. Duplicate/conflicting/incomplete datasets block deterministic money conclusions.
6. **Recompute deterministically** — supported base → rate/tier → expected → reported → paid → variances. Every run is bound to agreement version, engine version, input hash and tested period.
7. **Emit one fail-closed state** — NO_DEFENSIBLE_RECOVERY / RECOVERY_CANDIDATE / UNKNOWN / NEEDS_DATA / REQUIRES_PROFESSIONAL_REVIEW.
8. **Record qualitative risk evidence** — use sourced risk factors as unweighted signals until outcome evidence supports calibration. Do not invent numeric weights.
9. **Portfolio triage** — output NO_CURRENT_RECOVERY_SIGNAL / NEEDS_DATA / PROFESSIONAL_REVIEW / READY_FOR_DESK_REVIEW / FORMAL_AUDIT_CANDIDATE. Clean cases must remain visible.
10. **Human review** — reviewer identity, role, decision and rationale are required before external action. Review can request data, reject, approve an analytical desk finding, route to formal audit, or require professional review.
11. **Formal-audit handoff** — when the agreement/professional boundary requires a qualified auditor or access to licensee books, supply the source-linked evidence/calculation pack and unresolved questions without relabeling the internal screen as the formal audit.
12. **Outcome ledger** — record later professional findings, revised calculations, settlement/payment evidence, verified incremental recovery, fees, elapsed time and final outcome.
13. **Feedback loop** — compare triage to real outcomes, record false positives/negatives, refine evidence requirements, and calibrate risk only from validated outcomes.

## Current implementation coverage

Implemented: deterministic engine; fail-closed states; deadline assessment; portfolio triage; sourced unweighted risk catalog; evidence pack; human review gate; tenant-scoped persistence for organizations/parties/agreements/versions/evidence; calculation-run staleness; authenticated tenant API; synthetic portfolio testing.

Not yet implemented: secure binary file storage; automatic clause extraction; full transaction-level SKU/territory/channel normalization; bundle and related-party mechanics; interest engine; persistent finding/review/outcome workflow through the API; partner portal; real customer delivery.

## Gate 5 pass condition

Gate 5 passes only when this method reproducibly processes a complete synthetic portfolio end-to-end through persistence, review, stale-run behavior and an exportable evidence pack with all P0 false-recovery traps green. A written method alone is not success.
