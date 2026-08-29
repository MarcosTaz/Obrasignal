# Aviation Lease Entitlement Recovery — Fleet BATON

STATUS: ACTIVE
FACTORY_ID: aviation-lease-entitlement-recovery
REPOSITORY: MarcosTaz/Obrasignal
CANONICAL_APP_BRANCH: apps/aviation-lease-entitlement-recovery
CANONICAL_APP_HEAD_OBSERVED: 0d1759832a06b3177b67b35a4c53ee0c69db459e
PREDECESSOR_PR: #778
PREDECESSOR_HEAD: 088eaa3cd79cba1a62c7d905bd6d9cf831de21a5
VERIFIED_SUCCESSOR_PR: #786
VERIFIED_SUCCESSOR_BRANCH: aviation/evidence-backed-pilot-intake-refresh-20260829
VERIFIED_SUCCESSOR_HEAD: 5e34250396fd15701298e533643370459d1efff2
SUCCESSOR_STATUS: DRAFT / DO NOT MERGE / NOT CANONICAL / EXACT-HEAD GREEN

MISSION
Advance the assisted lessee-side maintenance-reserve recoverability wedge without turning arithmetic, documentary presence, or candidate review state into entitlement or recovery claims.

CURRENT_TRUTH
- `pilot.json` is assisted-mode with `production_authority=false`.
- Required pilot inputs include lease contract, maintenance-event evidence, eligible cost, reimbursed amount, and notice due.
- Pricing remains HYPOTHESIS only: EUR 5k–25k audit fee and 15–25% success fee; WTP is not proven.
- #786 provides the current-base aviation-specific evidence-backed intake boundary: immutable SHA-256 document identity, explicit provenance, explicit evidence-use authorization, tenant identity and actor identity.
- Positive unreimbursed arithmetic is only `CANDIDATE_READY_FOR_HUMAN_REVIEW`; entitlement remains `UNKNOWN`, recovery remains `NOT_ESTABLISHED`.
- Zero unreimbursed balance remains `EVIDENCE_OR_ECONOMICS_UNRESOLVED`.
- No real airline/lessor/customer evidence was used.

VERIFICATION
- Old #778 exact HEAD: compile success, mobile SUCCESS, Python full-repository FAILURE with 12 failures / 847 passed / 2 skipped.
- Job logs prove those 12 failures were Factory Cloud inventory/orchestrator expectation drift; none was `tests/test_aviation_pilot_intake.py`.
- Current canonical app base `0d1759832a06b3177b67b35a4c53ee0c69db459e`: Python SUCCESS + Mobile SUCCESS.
- Successor #786 exact HEAD `5e34250396fd15701298e533643370459d1efff2`: ObraSignal Quality run `33266289206`, Python SUCCESS + Mobile SUCCESS.
- Therefore the evidence-backed aviation intake is PASSING_AFTER_PROVEN on current repository truth, but remains non-canonical until owner adoption/merge.

ACTIVE
Extend the verified assisted-pilot candidate with one synthetic, permission-explicit end-to-end review/outcome fixture while preserving UNKNOWN entitlement and NOT_ESTABLISHED recovery until authorized human evidence supports a stronger state.

NEXT
1. Prove synthetic evidence identity → arithmetic → human review boundary → outcome/no-recovery recording end to end.
2. Fail closed on missing authorization/provenance, cross-tenant composition, stale/mismatched evidence identity, or unsupported review transition.
3. If the new invariant reveals a deterministic aviation-specific defect, freeze failing-before evidence and repair separately.

WAIT
- Real lease contract and maintenance-event evidence with explicit customer permission.
- Human pilot review and observed real outcome/no-recovery.
- Delivery-cost measurement.
- Pricing/WTP validation.
- Merge/adoption/deploy/production authority.

BLOCKERS
External pilot evidence/WTP remain unavailable and must not be fabricated. They do not block repository-safe synthetic verification or other Factories.

EXACT_NEXT_EXECUTABLE_ACTION
On a repository-safe successor stacked from #786, add a synthetic permission-explicit end-to-end assisted-pilot fixture covering evidence identity, arithmetic, review and outcome/no-recovery persistence; obtain exact-head CI. No merge, deploy, production data, secrets, provider/config changes, source activation, or external outreach.
