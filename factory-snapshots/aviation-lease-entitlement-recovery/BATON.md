# Aviation Lease Entitlement Recovery — Fleet BATON

STATUS: ACTIVE
FACTORY_ID: aviation-lease-entitlement-recovery
REPOSITORY: MarcosTaz/Obrasignal
CANONICAL_APP_BRANCH: apps/aviation-lease-entitlement-recovery
CANONICAL_APP_HEAD_OBSERVED: 0d1759832a06b3177b67b35a4c53ee0c69db459e
CANDIDATE_PR: #778
CANDIDATE_BRANCH: aviation/evidence-backed-pilot-intake-20260829
CANDIDATE_HEAD: 088eaa3cd79cba1a62c7d905bd6d9cf831de21a5
CANDIDATE_STATUS: DRAFT / DO NOT MERGE / NOT CANONICAL

MISSION
Advance the assisted lessee-side maintenance-reserve recoverability wedge without turning arithmetic, documentary presence, or candidate review state into entitlement or recovery claims.

CURRENT TRUTH
- pilot.json is assisted-mode, production_authority=false.
- Required pilot inputs include lease contract, maintenance-event evidence, eligible cost, reimbursed amount, and notice due.
- Pricing remains HYPOTHESIS only: EUR 5k–25k audit fee and 15–25% success fee; no WTP proof is recorded here.
- PR #778 adds an aviation-specific evidence-backed pilot intake boundary requiring immutable SHA-256 content identity, provenance, explicit evidence-use authorization, tenant identity, and actor identity.
- Positive unreimbursed arithmetic is classified only as CANDIDATE_READY_FOR_HUMAN_REVIEW; entitlement stays UNKNOWN and recovery stays NOT_ESTABLISHED.
- Zero unreimbursed balance stays EVIDENCE_OR_ECONOMICS_UNRESOLVED.
- No real airline/lessor/customer evidence was used.

VERIFICATION
- Candidate exact HEAD 088eaa3cd79cba1a62c7d905bd6d9cf831de21a5 compiled successfully.
- Mobile CI: SUCCESS.
- Python full-repository CI: FAILURE, 12 failed / 847 passed / 2 skipped.
- The 12 failures are not in tests/test_aviation_pilot_intake.py. They are pre-existing/drift-sensitive Factory Cloud inventory/orchestrator expectations (including ContractCredit registration and shared-core state assumptions) on the candidate's older base snapshot.
- Current canonical app branch HEAD 0d1759832a06b3177b67b35a4c53ee0c69db459e has Python SUCCESS and Mobile SUCCESS, so the candidate CI failure must not be classified as an aviation-intake defect without a refreshed exact-head proof.

EVIDENCE
- PR #778: evidence-backed assisted pilot intake.
- CI run 33263213387 on candidate HEAD: python FAILURE / mobile SUCCESS.
- Current app HEAD check run 33264421114: python SUCCESS / mobile SUCCESS.

ACTIVE
Refresh/replay the evidence-backed aviation intake candidate on top of the current canonical app branch, preserving the exact fail-closed semantics, then obtain exact-head Python + Mobile proof.

NEXT
If refreshed exact-head is GREEN, extend the assisted-pilot packet with a synthetic, permission-explicit end-to-end review fixture that proves evidence identity → arithmetic → human review boundary → outcome/no-recovery record without asserting entitlement. If RED only in newly introduced aviation invariants, freeze deterministic failing-before evidence and repair on a separate repository-safe branch.

WAIT
- Real lease contract and maintenance-event evidence with explicit customer permission.
- Human pilot review and observed outcome/no-recovery.
- Delivery-cost measurement.
- Pricing/WTP validation.
- Merge/adoption/deploy/production authority.

BLOCKERS
- PR #778 is stale relative to the current app branch and therefore not fully verified at current repository truth.
- External pilot evidence/WTP remain unavailable and must not be fabricated.

ASSUMPTIONS
- The repository app branch is the current technical source of truth for this vertical; no stronger canonical BATON was found during reconstruction.
- Existing PR #778 semantics are candidate evidence only until refreshed exact-head verification.

EXACT_NEXT_EXECUTABLE_ACTION
Create a repository-safe successor from current apps/aviation-lease-entitlement-recovery, port only the three #778 aviation-intake changes, run/observe exact-head CI, and classify GREEN vs deterministic aviation-specific RED. No merge, deploy, production data, secrets, provider/config changes, source activation, or external outreach.
