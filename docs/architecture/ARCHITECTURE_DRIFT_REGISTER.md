# ObraSignal Architecture Drift Register

**Sentinel baseline:** `main@fce51d5b5524e09691f9187f7619ea0166217487`  
**Captured:** 2026-08-25  
**Rule:** only repository/PR-proven findings belong here. Open items are not merge authorization.

## AS-DRIFT-001 — Expired opportunity can remain commercially actionable

- **Priority:** P1
- **Category:** DATA MODEL DRIFT / RUNTIME DRIFT / PRODUCT TRUTH
- **State at baseline:** DEGRADED
- **Affected owner:** SIGNAL / Opportunity Lifecycle + Opportunity API/read model
- **Proof:** canonical actionability filters used `COALESCE(lifecycle.is_actionable,1)=1`; absence of lifecycle therefore evaluated true even when the known submission deadline was already expired. Detail independently reported the deadline as closed, producing contradictory truth.
- **Customer risk:** a contractor can be shown expired work as a current actionable opportunity.
- **Repair:** Sentinel PR `#214` centralizes effective actionability precedence and adds regression coverage across feed/detail, stats, legacy read model and event generation.
- **Status:** REPAIR_PR_OPEN / NOT MERGED.
- **Integration handoff:** Golden Path issue `#210` must be rerun on the combined repair tree. Any strict expected-failure marker must be deliberately updated only after the defect is actually fixed.

## AS-DRIFT-002 — Authenticated production identity remains degraded

- **Priority:** P0/P1 boundary (security availability; no authorization bypass observed)
- **Category:** SECURITY DRIFT / PRODUCTION-CONFIG DRIFT
- **State:** DEGRADED / PRODUCTION_VALIDATED=NO
- **Affected owner:** Auth / production provider integration
- **Proof:** PR `#211` records that deployed merged SHA `fce51d5b...` passes unauthenticated/malformed-token boundaries but a valid real Supabase ES256 token still receives `401 authentication_required`; provider health is degraded. The verifier remains fail-closed.
- **Customer risk:** legitimate authenticated production use is blocked; no evidence supports calling production authentication healthy.
- **Repair path:** PR `#211` adds bounded secret-free JWKS failure diagnostics and is exact-head tested, but is not deployed.
- **Status:** BLOCKED on an authorized integration/deployment step and subsequent real production E2E. Sentinel must not mutate production or secrets.

## AS-DRIFT-003 — Compare branch violates authoritative money invariants

- **Priority:** P2 while branch-only; P1 if proposed for integration without repair
- **Category:** CONTRACT DRIFT / MONEY INVARIANT / PR HEALTH
- **State:** BLOCKED
- **Affected owner:** Compare PR `#151`
- **Proof:** temporary adversarial bisections `#201` and `#202` isolate non-finite number handling and binary-float precision loss in the Compare candidate. Golden Path PR `#207` consequently excludes Compare from accepted product truth.
- **Risk:** authoritative monetary comparison can accept NaN/Infinity or lose Decimal precision.
- **Status:** BRANCH-ONLY / DO NOT INTEGRATE until the owning feature is repaired and exact-head retested. Sentinel does not rewrite the feature branch from main without preserving feature ownership.

## AS-DRIFT-004 — Accepted ADR encoded stale Master Queue state

- **Priority:** P3
- **Category:** DOCUMENTATION DRIFT
- **State at baseline:** DEGRADED
- **Proof:** ADR 0001 stated `Q040 CanadaBuys remains active`; canonical `master_execution_queue.py` declares `Q040_CANADA_BUYS` DONE and `Q080_EVIDENCE_GRAPH_V1` as the sole ACTIVE item.
- **Risk:** architectural documentation could be mistaken for execution authority.
- **Repair:** Sentinel architecture-fitness PR replaces the volatile item-specific statement with the durable rule that execution priority is owned exclusively by `master_execution_queue.py`.
- **Status:** REPAIR_PR_OPEN / NOT MERGED.

## AS-DRIFT-005 — Source stable-identity uniqueness lacked a generic fitness gate

- **Priority:** P2 prevention
- **Category:** TEST DRIFT / REGISTRY DRIFT PREVENTION
- **State at baseline:** DEGRADED (protection gap; no duplicate current source_id proven)
- **Proof:** `test_source_registry.py` contains source-specific contracts and production-gate checks but no whole-registry invariant rejecting duplicate/missing stable `source_id` values; a Python dict also silently overwrites duplicate literal keys before runtime validation can see them.
- **Risk:** parallel source work can create aliases/duplicate stable identities or silently replace a literal registry key without a deterministic architecture failure.
- **Repair:** `architecture_audit.py` validates non-empty unique source identities and statically detects duplicate literal keys in source/capability registries before Python overwrite.
- **Status:** REPAIR_PR_OPEN / NOT MERGED.

## AS-DRIFT-006 — Open PR graph contains non-production validation assemblies

- **Priority:** P2 integration safety
- **Category:** PR-SUPERSESSION / COMBINATION RISK
- **State:** CONFLICT-RISK, not a main runtime defect
- **Proof:** PR `#209` explicitly declares itself a temporary cumulative Integration Lab validation PR with **DO NOT MERGE**, and its tree includes multiple feature candidates plus integration-owned corrective glue. Other open Integration/Golden Path bisection PRs similarly carry common history and already-absorbed Auth commits.
- **Risk:** treating changed-file overlap or green CI as merge authorization can duplicate/supersede canonical changes or import integration-only glue as product ownership.
- **Required handling:** classify temporary validation PRs separately from product candidates; compare effective delta against current main and named owner PRs before any assembly decision.
- **Status:** TRACKING / Integration Lab owner for combination validation.

# Architecture Health — baseline SHA

| Domain | State | Evidence / current action |
| --- | --- | --- |
| Master Queue | HEALTHY | Canonical validator enforces one ACTIVE item, valid `CURRENT_ITEM_ID`, dependencies and cycles. |
| Canonical ownership | DEGRADED | Core owners are identifiable, but the large open-PR graph needs explicit supersession classification before assembly. |
| Capability registry | HEALTHY on main | Registry validator exists; no current main violation proven. |
| Source registry | HEALTHY current data / DEGRADED protection | No current duplicate stable identity proven; generic identity fitness was missing and is added by Sentinel. |
| Runtime composition | HEALTHY repository-declared | One Flask constructor and `gunicorn cors_app:APP`; production deployment validation is separate. |
| Auth / tenant | DEGRADED production | Request identity is server-derived/fail-closed, but real production provider authentication remains degraded per #211. |
| Persistence / migrations | HEALTHY with watch item | Single repository-declared SQLite store; additive `ensure_*` schema evolution. No destructive migration found in this pass. |
| Opportunity lifecycle | DEGRADED on main | AS-DRIFT-001; repair #214 open. |
| PR graph | DEGRADED | 59 open PRs at pass start with feature, research, temporary integration and adversarial branches. |
| Documentation truth | DEGRADED at baseline | AS-DRIFT-004; repair included in Sentinel fitness PR. |
| Architecture test protection | DEGRADED at baseline | No repeatable architecture audit command; repair adds one plus CI gate. |
| Production configuration | UNKNOWN/DEGRADED | Repo configuration is inspectable; real authenticated production validation currently fails. |

## Unresolved architecture conflicts

No conflict in this pass authorizes a structural rewrite. The following require owner/integration decisions rather than silent Sentinel choice:

1. Evidence foundation/product integration (`#147` + `#194`) must be reconciled onto current main Auth/runtime without wholesale canonical-file replacement.
2. Compare `#151` must resolve its money contract failures before combination acceptance.
3. Temporary Integration Lab trees such as `#209` must remain validation artifacts unless an explicit canonical assembly process extracts owned fixes.
4. Production Auth follow-up `#211` requires authorized integration/deployment before its diagnostics can identify the Render-side provider failure category.
