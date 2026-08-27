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
- #636@`c20bc9cc4c2aa9d73752d467cac524e364261b5f`: Watchlist owner persistence semantics on #630; Quality `33118785478` Python+Mobile SUCCESS.
- #637@`98c22d369f7892bebd0241cfe29e9058214e7b72`: Pursuit Workspace owner surface + behaviorally enforced SQLite FK; Quality `33119211007` Python+Mobile SUCCESS.
- #638@`69aae936937622454b3602cfa6ae8a0da3ffcdf2`: Q090 Company State owner contract on #630; Quality `33119282884` Python+Mobile SUCCESS; PREBUILD preserved.
- #639@`d0817e5cd439d9f640ad19f3a8fa2cd2a6231a1b`: Q090 × exact #238 persistence reliability; Quality `33119563902` Python+Mobile SUCCESS; serialized first-start, tenant isolation, corruption fail-closed, verified backup→restore.

## CURRENT FAILING-BEFORE
#640@`262af7793eb84f909a961d060ab2347e4d0b5a5c`, Quality `33119660299`: Mobile SUCCESS; Python exactly 2 failed / 883 passed / 2 skipped.
- Watchlist `priority`/`saved_at` additive migrations are executable but absent from #238 `REGISTERED_ADDITIVE_MIGRATIONS`.
- Pursuit Workspace four-table family is executable but absent from #238 `KNOWN_TABLE_OWNERS`.
Classification: `PRODUCT_OWNER_STORAGE_GREEN != PERSISTENCE_OWNER_REGISTRATION_GREEN`.

## ACTIVE
#641@`30acf05838eba3fb4c1197f26dcc22f9cca246a4` — integration-only passing-after composition for #640. Exact #238 registry is preserved as `storage_contract_base.py`; wrapper extends that same registry for Watchlist additive columns/indexes and Pursuit PREBUILD ownership. Quality `33119871501` queued at baton write.

## RESUME_AT
Fetch jobs for Quality `33119871501`. If Python+Mobile GREEN, classify #640 registration gaps `PASSING_AFTER_PROVEN_ON_#641_INTEGRATION / NOT CANONICAL`, route exact result to #238, then continue deeper Watchlist/Pursuit #238 reliability acceptance (shared serialized first-start, partial/concurrent-first, tenant/cross-tenant, backup→restore). If RED, inspect exact Python logs and repair the #641 integration without weakening #640 assertions.

## OWNER DEPENDENCIES / BOUNDED GREENS
- Watchlist #632 failing-before -> #636 narrow owner passing-after GREEN. Storage registration is separately RED in #640 until #641 validation.
- Pursuit #633 failing-before -> #637 owner/FK behavior passing-after GREEN. Storage registration is separately RED in #640 until #641 validation.
- Q090 #634 failing-before -> #638 owner passing-after GREEN -> #639 Persistence reliability GREEN. Q090 remains PREBUILD/no runtime/API registration.
- Billing temporal #628 failing-before -> #629 provider-snapshot authority GREEN; #630 preserves it.
- Exact decision→event + provider-ticket parentage and persistence restore are GREEN candidates inside #630.
- Source durability/completeness/external-time/normalization provenance + Notification/Mobile truth remain GREEN candidates in the trust spine.
- Physical device/user delivery remains UNKNOWN/external; provider acceptance != delivery.
- US_SAM commercial reuse remains YELLOW/fail-closed, not GREEN.

## NEXT
1. Finish #641 exact-head classification and #238 routing.
2. Build Watchlist persistence reliability acceptance beyond schema: shared serialized first-start, partial/concurrent-first, tenant A/B mutations, backup→restore.
3. Build Pursuit persistence reliability acceptance: shared startup authority, tenant/cross-tenant, orphan/cascade semantics, backup→restore.
4. Selectively revalidate #631/#635 only if their input tree moves.

## WAIT
Only genuine external/owner-only boundaries: merge/deploy/prod/provider/config/secrets/real customer/source activation; physical-device delivery evidence; stronger source-scoped legal authority for US_SAM GREEN.
