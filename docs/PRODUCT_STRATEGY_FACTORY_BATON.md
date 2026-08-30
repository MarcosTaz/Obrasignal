# Product Strategy, Capability & Roadmap Factory — BATON

STATUS: ACTIVE / REPOSITORY_ONLY / NOT_CANONICAL

MISSION: preserve an evidence-gated product strategy that improves contractor decisions without turning roadmap language into unsupported product or market claims.

VERSION / HEAD BEFORE BATON: 6e008b88b98615e9ee08a1d2a18d1d10f2ea41e8
BRANCH: strategy/contractor-decision-superiority-v1
PR: #521 (OPEN / DRAFT / NOT MERGED)

CURRENT TRUTH
- Product-superiority strategy exists as a documentation-only candidate.
- Exact-head ObraSignal Quality run 33317486925 is SUCCESS at 6e008b88b98615e9ee08a1d2a18d1d10f2ea41e8.
- docs/PRODUCT_STRATEGY_EVIDENCE_MATRIX_v0.1.json exists and fail-closes missing external evidence to UNKNOWN.
- The matrix separates repository capability, synthetic proof, external proof and canonical status across decision quality, lead-time advantage, buyer/competitor intelligence, economic pursuit, execution readiness, market depth and distribution.
- Distribution superiority, customer outcomes and willingness-to-pay remain UNPROVEN.
- Canonical execution authority remains outside this strategy document; this branch does not supersede domain owners or the master execution queue.

DONE
- Created the synthetic strategy-evidence matrix with explicit evidence classes and no real-customer claims.
- Repaired the mobile Expo/RN dependency drift on this branch.
- Verified exact-head ObraSignal Quality SUCCESS at the current source head before this metadata-only BATON refresh.

ACTIVE
Reconcile the evidence matrix against adjacent Customer Decision, Analytics and GTM repository truth and identify the highest-value capability whose current repository status is materially stale or unsupported.

NEXT
Inspect the current Analytics and Customer Decision evidence contracts, then update only Product Strategy rows whose repository capability/canonical status can be proven from exact repository evidence. Do not infer market proof from code or synthetic tests.

WAIT
- Canonical adoption / merge decision.
- Real customer outcomes, WTP, distribution and retention evidence.
- Domain-owner semantics for capabilities that are not yet canonical.

BLOCKERS
None for repository-safe strategy/evidence reconciliation.

EVIDENCE
- PR #521 source head 6e008b88b98615e9ee08a1d2a18d1d10f2ea41e8 before this BATON-only refresh.
- ObraSignal Quality run 33317486925: SUCCESS at that exact head.
- docs/PRODUCT_STRATEGY_EVIDENCE_MATRIX_v0.1.json on branch.
- Product superiority forensic gap map on branch.

ASSUMPTIONS
- Strategy documents are non-authoritative until separately reconciled/adopted.
- UNKNOWN remains preferable to false precision.
- A metadata-only BATON update does not itself prove CI GREEN for the successor commit.

EXACT NEXT EXECUTABLE ACTION
Open the current Analytics evidence contract and Customer Decision evidence contract, compare their exact repository statuses with docs/PRODUCT_STRATEGY_EVIDENCE_MATRIX_v0.1.json, and make only evidence-backed row updates; then validate JSON and re-run exact-head Quality via the resulting branch commit.
