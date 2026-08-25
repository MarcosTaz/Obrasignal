# ObraSignal Architecture Drift Register

**Canonical baseline rechecked:** `main@fce51d5b5524e09691f9187f7619ea0166217487`  
**Captured / rechecked:** 2026-08-25  
**Rule:** only repository/PR-proven findings belong here. Open items are not merge authorization. Exact-head evidence belongs only to the SHA tested.

## AS-DRIFT-001 — Expired opportunity can remain commercially actionable

- **Priority:** P1
- **Category:** DATA MODEL DRIFT / RUNTIME DRIFT / PRODUCT TRUTH
- **State on main:** DEGRADED
- **Affected owner:** SIGNAL / Opportunity Lifecycle + Opportunity API/read model
- **Proof:** canonical actionability filters default missing lifecycle to actionable even when a known submission deadline is expired; detail can independently report a closed deadline, producing contradictory customer truth.
- **Customer risk:** a contractor can be shown expired work as a current actionable opportunity.
- **Repair:** Sentinel PR `#214` centralizes effective actionability precedence across feed/detail/stats/legacy read model/events and preserves historical visibility.
- **Adversarial repair finding:** the first repair still let the API coerce a date-only deadline to midnight. The current repair preserves DATE precision on the current day as `deadline_status=unknown`, `is_actionable=true`, `is_open=false` rather than inventing midnight or 23:59.
- **Current exact repair HEAD:** `310a5ade0b6da31b53c34a226c5b433bb1ef9767`.
- **Exact-head Quality:** run `32851557467` = SUCCESS (Python + Mobile).
- **Status:** TESTED / REPAIR_PR_READY / NOT MERGED / NOT DEPLOYED.
- **Integration handoff:** Golden Path issue `#210` must be rerun on the combined repair tree. Strict expected-failure markers may change only after the combination proves the repaired behavior.

## AS-DRIFT-002 — Authenticated production identity remains degraded

- **Priority:** P0/P1 boundary (security availability; no authorization bypass observed)
- **Category:** SECURITY DRIFT / PRODUCTION-CONFIG DRIFT
- **State:** DEGRADED / PRODUCTION_VALIDATED=NO
- **Affected owner:** Auth / production provider integration
- **Proof:** deployed merged SHA `fce51d5b...` passes unauthenticated/malformed-token boundaries but a valid real Supabase ES256 token still receives `401 authentication_required`; verifier behavior remains fail-closed.
- **Repair path:** PR `#211` adds bounded secret-free provider/JWKS diagnostics and hardens the verifier boundary. Its current branch is exact-head Quality/live-gate validated but not deployed.
- **Status:** OTHER_OWNER / external authorized integration+deployment gate. Sentinel must not mutate production or secrets.

## AS-DRIFT-003 — Compare money defect was repaired; historical bisections are superseded evidence

- **Priority:** P2 integration history
- **Category:** MONEY INVARIANT / PR-SUPERSESSION
- **State:** SUPERSEDED DEFECT / CURRENT OWNER CONTRACT CORRECTED
- **Affected owner:** Compare PR `#151`
- **Historical proof:** adversarial bisections `#201` and `#202` isolated non-finite handling and binary-float precision loss.
- **Current proof:** `#151` now uses Decimal-backed money parsing and rejects booleans, non-finite and negative values; current-main temporary integration PR `#217` validated the corrected Compare-owned files on exact head `34f8cc1f8c9f08f2a7c621fb36d637a502e1627b` with Quality success, then closed unmerged as intended.
- **Status:** #201/#202 are historical bisection evidence, not merge candidates. #151 still requires normal integration handling because its long-lived branch history/mergeability is separate from money correctness.

## AS-DRIFT-004 — Accepted ADR encoded stale Master Queue state

- **Priority:** P3
- **Category:** DOCUMENTATION DRIFT
- **State on main:** DEGRADED
- **Proof:** ADR 0001 states `Q040 CanadaBuys remains active`; canonical `master_execution_queue.py` declares `Q040_CANADA_BUYS` DONE and `Q080_EVIDENCE_GRAPH_V1` as the sole ACTIVE item.
- **Repair:** Sentinel architecture-fitness PR replaces the volatile item-specific statement with the durable law that execution priority is owned exclusively by `master_execution_queue.py`.
- **Status:** REPAIR_PR_OPEN / NOT MERGED.

## AS-DRIFT-005 — Source stable-identity uniqueness lacked a generic fitness gate

- **Priority:** P2 prevention
- **Category:** TEST DRIFT / REGISTRY DRIFT PREVENTION
- **State on main:** DEGRADED protection; no duplicate current `source_id` proven
- **Proof:** source-specific tests did not provide one whole-registry invariant for non-empty unique stable `source_id`; Python dict literals can silently overwrite duplicate literal keys before runtime validation.
- **Repair:** `architecture_audit.py` validates non-empty unique stable source identities and statically detects duplicate source/capability literal keys before overwrite.
- **Status:** TESTED on Sentinel PR #216 exact head; NOT MERGED.

## AS-DRIFT-006 — Temporary integration/acceptance PRs are not production candidates

- **Priority:** P2 integration safety
- **Category:** PR-SUPERSESSION / COMBINATION RISK
- **State:** DEGRADED PR graph, not a main runtime defect
- **Proof:** many Integration Lab / Golden Path PRs explicitly state `DO NOT MERGE`, contain multi-parent/current-main assemblies or adversarial-only tests. The open PR count changed materially during this pass (59 at the first snapshot, 74 at a later exact search) while `main` stayed unchanged.
- **Risk:** green CI, branch existence or changed-file overlap can be mistaken for ownership/merge authorization.
- **Required handling:** classify temporary validation PRs separately; compare effective current-main delta and named owner PRs before assembly. PR-count movement alone is not architecture movement.

## AS-DRIFT-007 — France DECP owner branch replaces the canonical production composition root

- **Priority:** P1/P2
- **Category:** RUNTIME DRIFT / PRODUCTION-CONFIG DRIFT
- **State:** OTHER_OWNER DRIFT; safe integration reconciliation proven
- **Affected owner:** France DECP PR `#171`, HEAD `e8209221d21d30f009021f3088df8c0a172a78d7`
- **Proof:** #171 changes Render from canonical `cors_app:APP` to `france_app:APP` only to install FR_DECP. `france_app.py` reuses the same Flask object, so this is not a second Flask constructor, but it is a competing source-specific production composition/startup root.
- **Risk:** repeated `country_app:APP` patterns make integration order decide which runtime installers exist and create parallel deployment truth.
- **Handoff:** Sentinel commented on #171: keep Render on `cors_app:APP`, install FR_DECP through the canonical public source/runtime composition seam.
- **Combination proof:** temporary PR `#230` removes `france_app.py`, restores `cors_app:APP`, installs France additively, and passes exact-head Quality plus France live smoke at `59eefd712f1f87fd2cdcb668835fd702befbc7c6`.
- **Status:** #230 is COMBINATION_VALIDATED temporary evidence, not automatic merge authorization.

## AS-DRIFT-008 — Requirements implementation maturity is encoded as rollout maturity

- **Priority:** P2
- **Category:** CAPABILITY REGISTRY DRIFT / QUEUE GOVERNANCE
- **State:** OTHER_OWNER
- **Affected owner:** Requirements PR `#152`, HEAD `f39241556fb40b72c41b192a08368bd71d4bd2ea`
- **Proof:** the PR explicitly says `Q110_DYNAMIC_ELIGIBILITY_RESEARCH` remains queued RESEARCH and that it does not promote the item, while the same branch registers `REQUIREMENTS` as `PILOT`.
- **Risk:** code/test readiness can be mistaken for rollout permission before canonical queue/dependency gates.
- **Handoff:** Sentinel requested `RESEARCH` (or no registration until a distinct canonical ownership decision) and a regression preventing code existence from silently promoting maturity.

## AS-DRIFT-009 — Opportunity Change History can activate persistence/runtime outside an explicit queue item

- **Priority:** P2
- **Category:** QUEUE DRIFT / CAPABILITY DRIFT / RUNTIME DRIFT
- **State:** OTHER_OWNER
- **Affected owner:** Change History PR `#155`, HEAD `7f9ba460b5955ef2bb0b9dcd822d8cd14bba8e3d`
- **Proof:** branch registers `OPPORTUNITY_CHANGE_HISTORY=PILOT`; `source_runtime.py` persists history whenever state is `PILOT|ENABLED`; no corresponding canonical queue item was found and the branch deliberately leaves the Master Queue unchanged.
- **Impact:** integrating the branch as-is would add three history tables and a fail-closed dependency to source transactions solely through feature-branch registry maturity.
- **Handoff:** Sentinel requested keeping the implementation inert/RESEARCH until Assembly/queue governance assigns canonical ownership/dependencies and explicitly promotes it.

## AS-DRIFT-010 — Readiness loses temporal precision for date-only deadlines

- **Priority:** P2 branch-only; P1 if exposed as product truth
- **Category:** TIME INVARIANT / CONTRACT DRIFT / FALSE CUSTOMER CLAIM
- **State:** OTHER_OWNER DEFECT
- **Affected owner:** Readiness PR `#153`, current observed HEAD `5cfb2c3e751c19b59ca0a98e8d438a90bd0271c1`
- **Proof:** `_parse_deadline(date(...))` invents `23:59:59 UTC`; `_parse_deadline("YYYY-MM-DD")` invents `00:00 UTC`. Identical source-date evidence therefore changes business state solely by Python representation.
- **Golden Path:** #215 captures `BUG-GP-READINESS-DATE-001` as strict expected failure.
- **Handoff:** preserve explicit DATE vs EXACT_DATETIME precision; same-day date-only with unknown closing time/timezone must not become exact OPEN/EXPIRED.

## AS-DRIFT-011 — MOBILIZE omission becomes verified accommodation availability

- **Priority:** P2 branch-only
- **Category:** CONTRACT DRIFT / UNKNOWN→AVAILABLE / FALSE CUSTOMER CLAIM
- **State:** OTHER_OWNER DEFECT
- **Affected owner:** MOBILIZE PR `#146`, HEAD `8ae8894fc86e7c7b6daeabe8bc7fd64e59fecb10`
- **Proof:** `MobilizationContext.hotel_available: bool = True`; omission is therefore indistinguishable from explicit verified availability and can leave accommodation-dependent scenarios available/comparable.
- **Golden Path:** #218 captures `BUG-GP-MOBILIZE-AVAIL-001` as strict expected failure.
- **Handoff:** use an explicit tri-state availability contract; UNKNOWN must not become AVAILABLE. Q222 remains GATED/RESEARCH.

## AS-DRIFT-012 — Q090 current prebuild head is red, historical green evidence does not transfer

- **Priority:** P2 PR health / integration gate
- **Category:** TEST DRIFT / EXACT-HEAD
- **State:** OTHER_OWNER / CURRENT HEAD NOT TESTED GREEN
- **Affected owner:** Q090 Company State PR `#223`
- **Observed current HEAD:** `7725b2ec6e986d0f4eb867cba091b99e13ddf529`
- **Quality:** run `32851902722`: compile PASS, Mobile PASS, repository pytest step FAIL.
- **Root cause:** not proven from available job metadata; Sentinel did not guess.
- **Architecture note:** Q090 remains a legitimate queued prebuild because its manifest declares `RUNTIME REGISTRATION=NONE`, canonical files are untouched and Q090 remains QUEUED behind Q080.
- **Handoff:** owner must inspect the failing pytest assertion and obtain new exact-head full Quality before any TESTED/integration-ready claim.

# PR supersession / lifecycle facts

These are repository/PR-proven relationships; they do not authorize closing or merging another cell's PR.

- **#207 SUPERSEDED BY #212** for Golden Path acceptance infrastructure. #212 explicitly calls itself the clean replacement and carries only acceptance-owned files. Preserve #207/#208 as historical validation evidence.
- **#201/#202 SUPERSEDED AS ACTIVE DEFECT PROBES** by the corrected #151 money contract plus current-main combination validation #217. Preserve them as adversarial provenance.
- **#176 + #196 implementation overlap CONSOLIDATED BY #197** for the LATAM Dominican/Uruguay code path; unique source/live evidence in the earlier PRs remains historical evidence.
- **#171 runtime wiring RECONCILED IN TEMPORARY #230** without replacing canonical `cors_app:APP`; this validates the semantic assembly shape but does not itself make #230 a product merge candidate.
- **Temporary cumulative Integration/Golden Path PRs (#199/#200/#203/#205/#208/#209 and successors)** are validation artifacts unless a canonical assembly explicitly extracts owner deltas. Never merge them merely because they are green.

# Architecture Health — current Sentinel baseline

| Domain | State | Evidence / current action |
| --- | --- | --- |
| Master Queue | HEALTHY on main | Canonical queue declares Q080 sole ACTIVE and enforces dependencies/state law. |
| Canonical ownership | DEGRADED across PR graph | Core main owners are identifiable; several branch-only maturity/runtime conflicts are handed off above. |
| Capability registry | HEALTHY on main / DEGRADED in specific branches | Main validator passes; #152/#155 branch states overreach queue maturity/activation. |
| Source registry | HEALTHY current main data / DEGRADED protection | No current duplicate stable identity proven; generic identity fitness exists on #216 but is not merged. |
| Runtime composition | HEALTHY on main / DRIFT in #171 | Main has one Flask constructor and `gunicorn cors_app:APP`; #230 proves safe France reconciliation. |
| Auth / tenant | DEGRADED production | Request identity remains server-derived/fail-closed in inspected main paths; production real-token auth is still degraded. |
| Persistence / migrations | HEALTHY on inspected main | One repository-declared SQLite store; additive `ensure_*` schema evolution; no destructive `DROP TABLE` found in the continuous pass. Branch #155 activation remains gated. |
| Opportunity lifecycle | DEGRADED on main | AS-DRIFT-001; exact-head tested repair #214 is open and unmerged. |
| Money semantics | HEALTHY for corrected Compare branch contract | Historical #201/#202 defects superseded; #217 current-main combination validation passed. |
| Time semantics | DEGRADED in branch candidates | #153 date-only Readiness defect; #214 repair explicitly protects date-only actionability/presentation. |
| PR graph | DEGRADED / fast-moving | Exact open-PR search reached 74 while main remained unchanged; temporary assemblies must stay non-canonical. |
| Documentation truth | DEGRADED | ADR stale queue wording repaired on #216; several temporary/acceptance PR bodies contain historical SHAs/status and must not be used as current truth without head recheck. |
| Architecture test protection | DEGRADED on main / TESTED on #216 | Repeatable architecture audit + strict CI exist only on Sentinel PR until integrated. |
| Production configuration | DEGRADED / not production-validated | Repository config is inspectable; authenticated production E2E remains unsuccessful on deployed main. |

## Unresolved architecture conflicts / owner gates

1. Evidence foundation/product integration (`#147` + `#194`) requires semantic current-main reconciliation; temporary #213 is combination evidence, not automatic merge authorization.
2. Production Auth follow-up `#211` requires authorized integration/deployment before Render-side provider diagnostics can be observed in production.
3. Requirements #152 and Change History #155 need maturity/queue reconciliation before canonical rollout.
4. Readiness #153 and MOBILIZE #146 have explicit Golden Path false-truth defects and must not promote around them.
5. Q090 #223 remains QUEUED and its observed current head is red; no historical green status may be promoted to that SHA.
6. Temporary Integration/Golden Path assemblies remain separate from product-owner PRs even when exact-head green.
