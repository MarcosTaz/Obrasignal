# ObraSignal Data-Truth Factory Baton

STATE: BATON_READY / CONTINUOUS / NONCANONICAL STATE FILE
CANONICAL_MAIN: `66d43f6fd51cf9cea08016dad335aaa04b711a24`
CURRENT_TRUST_BASE: #630@`9a294eb74ebc9ceaa06c4f4be32fb3b14b315216` — Quality `33112505148` SUCCESS
SAFETY: no automatic merge/deploy/prod/provider/config/secrets/real customer data/source activation.

## MISSION
Advance repository-first Data Integrity & Consistency; Data Lineage/Provenance/Auditability; Data Contracts/API Compatibility/Schema Evolution; Persistence/durability; Temporal Correctness; State Machines/Lifecycle; Source Health/Freshness; source→canonical integrity. Exact-head, evidence-first, fail-closed, preserve UNKNOWN.

## CURRENT PROVEN CANDIDATE SPINE
- #629@`3d26dd8244d48aca401bc3b0ad6279f66d6d4f4c`: Billing provider-snapshot temporal authority; Quality `33108377227` SUCCESS; noncanonical.
- #630@`9a294eb74ebc9ceaa06c4f4be32fb3b14b315216`: #629 + lineage persistence recovery; Quality `33112505148` SUCCESS; noncanonical.
- #631@`bb063959fba8ae2fe9b519c8222d53c66c718c60`: current-spine UNKNOWN coercion boundaries; Quality `33115690238` SUCCESS.
- #635@`a04a2015e4da6e0179be22590de74aa5da976f7d`: corrupt Source Health time + malformed Evaluation end fail closed; Quality `33117817881` SUCCESS.
- #636@`c20bc9cc4c2aa9d73752d467cac524e364261b5f`: Watchlist owner persistence semantics on #630; Quality `33118785478` Python+Mobile SUCCESS; noncanonical.
- #637@`98c22d369f7892bebd0241cfe29e9058214e7b72`: Pursuit Workspace owner surface + behaviorally enforced SQLite FK on #630; Quality `33119211007` Python+Mobile SUCCESS; noncanonical.

## ACTIVE
Q090 Company State current-spine owner reanchor: #638@`69aae936937622454b3602cfa6ae8a0da3ffcdf2` based on #630. Exact owner blobs: `company_state.py`=`2ebf8c03802833b29b2bc218e762c325b62546ce`; `company_state_store.py`=`367fbb693812b6406992422fb47c83045cb59158`; current-spine probe=`7892ade10bde47249658c3968ece5718a7fe43fb`. Quality run `33119282884` was IN_PROGRESS at baton write.

## RESUME_AT
Fetch jobs for Quality `33119282884`; if GREEN, update #638 to `PASSING_AFTER_PROVEN_ON_CURRENT_TRUST_COMPOSITION / PREBUILD / NOT CANONICAL`, route to #223 and #238, then expand Q090 with corruption/tenant/history/backup→restore acceptance without runtime/API promotion. If RED, inspect Python logs and repair/retest before unrelated work.

## CURRENT FAILING-BEFORE / OWNER DEPENDENCIES
- #632 Watchlist current-spine failing-before: 4 intended Python failures; now narrow passing-after #636 GREEN. Remaining #238 shared serialized startup, partial/concurrent-first, tenant A/B, backup→restore.
- #633 Pursuit Workspace current-spine failing-before: 3 intended Python failures; now #637 GREEN for owner surface/FK behavior. Remaining #238 shared connection/startup adoption, partial/concurrent-first, tenant A/B/cross-tenant, cascade policy, backup→restore.
- #634 Q090 current-spine failing-before: 2 intended Python failures; #638 validation in progress.

## HISTORICAL/CURRENT CANDIDATE DATA-TRUTH EDGES
- Exact decision→event + provider-ticket local parentage: #619 GREEN; migration/restore #622 GREEN; revalidated inside #630 GREEN.
- Source durability/completeness/external-time/normalization provenance + Notification/Mobile truth: #625/#627 GREEN candidates.
- Physical device/user delivery remains UNKNOWN/external; provider acceptance != delivery.
- US_SAM commercial reuse remains YELLOW/fail-closed, not GREEN.

## NEXT
1. Finish #638 exact-head classification and owner routing.
2. Build Persistence #238 acceptance compositions for #636/#637/#638: partial schema, concurrent-first under one shared startup authority, tenant isolation, corruption/orphan fail-closed, backup→restore.
3. Re-check #631/#635 only if their input trust spine changes.

## WAIT
Only genuine external/owner-only boundaries: merge/deploy/prod/provider/config/secrets/real customer/source activation; physical-device delivery evidence; stronger source-scoped legal authority for US_SAM GREEN.
