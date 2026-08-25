# ObraSignal Architecture Drift Register

**Canonical baseline rechecked:** `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`  
**Rule:** only current repository/PR-proven findings belong here. Historical green/failure evidence does not transfer across SHAs.

## RETIRED / HISTORICAL

- **AS-DRIFT-001 CLOSED→ACTIONABLE:** repaired by #214 and merged into current main. Historical repair-branch claims are retired.
- **AS-DRIFT-002 production Auth degraded:** retired. Production Auth and full authenticated E2E are validated on the current canonical lineage.
- **AS-DRIFT-012 Q090 observed-red head:** retired as current-state claim; exact-head status must always be re-read from its owner before integration.

## CURRENT SENTINEL FINDINGS

### AS-DRIFT-004 — stale ADR queue wording
- Category: DOCUMENTATION DRIFT.
- Repair in #216: durable rule that execution priority is owned exclusively by `master_execution_queue.py`.

### AS-DRIFT-005 — missing generic architecture fitness on main
- Category: TEST / REGISTRY / RUNTIME DRIFT PREVENTION.
- Current main has no canonical repository-wide strict audit for stable source identities, duplicate literal registry keys and runtime-entrypoint uniqueness.
- Repair candidate: #216, reconciled to current main; exact-head gates required after this reconciliation.

### AS-SEC-001 — canonical mutation control degraded
- Category: REPOSITORY SECURITY.
- Visible GitHub branch state reports `main protected=false`, protection disabled and no required checks; visible repository rulesets are empty.
- Prepared contract lives in #248 `ops/github-main-protection.json`; settings mutation is external and not performed by Sentinel without authorization.

### AS-SEC-002 — current-main supply chain degraded
- Category: SUPPLY CHAIN.
- Current main still contains mutable third-party Action refs in Auth/source/live workflows.
- Sentinel-owned cross-cutting repair candidate: #248.
- Auth/source-specific workflow fixes are routed to their existing owners and must not be absorbed into #216.

## CURRENT CANDIDATES

- **#216:** Architecture Fitness only. Reconciled architecture audit + current snapshot; no product/security feature absorption.
- **#248:** Security/Operability hardening. Current tested candidate; separate from #216 and not canonical until authorized integration.

## HEALTH

| Domain | State |
| --- | --- |
| Canonical runtime on current main | HEALTHY on inspected structure |
| Production Auth | VALIDATED |
| Opportunity actionability | REPAIRED on current main |
| Architecture fitness protection | DEGRADED on main / candidate #216 |
| Repository branch protection | DEGRADED / observably OFF |
| Current-main supply chain | DEGRADED / candidate #248 + owner handoffs |

No merge, settings mutation, production mutation, queue/capability/source promotion is authorized by this register.
