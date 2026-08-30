# Data, Analytics & Learning System Factory — BATON

STATUS: ACTIVE / REPOSITORY_ONLY / NOT_CANONICAL

MISSION: measure product, operational and commercial learning without converting missing evidence into zeros, rejection, success, or false precision.

VERSION / HEAD BEFORE BATON: de1509f3bae21cdcc6763e676df45407c220849c
BRANCH: analytics/measurement-truth-registry
PR: #344 (OPEN / DRAFT / NOT MERGED)

CURRENT TRUTH
- Commercial funnel logic explicitly keeps missing or partial owner evidence UNKNOWN.
- Adjacent OBSERVABLE owner counts may compute progression/dropoff rates; zero or missing authority cannot manufacture rates.
- docs/DATA_ANALYTICS_CROSS_FACTORY_MEASUREMENT_v0.1.json exists and codifies missing-is-UNKNOWN, synthetic-is-not-external-proof, owner/timestamp authority and negative cases.
- Exact-head ObraSignal Quality for de1509f3bae21cdcc6763e676df45407c220849c is SUCCESS (run 33317537026).
- Real replies, WTP, payment, retention, decision quality and outcome quality remain unproven unless supplied by their owning evidence source.

DONE
- Added cross-factory synthetic measurement handoff covering owner evidence, freshness, non-monotonic counts, unknown outcomes and synthetic-only evidence.
- Repaired mobile Expo/RN dependency drift on this branch.
- Verified exact-head Quality SUCCESS at the current source head before this metadata-only BATON refresh.

ACTIVE
Reconcile Analytics measurement contracts against current GTM and Customer Decision evidence ownership so cross-factory metrics cannot silently promote stale or noncanonical evidence.

NEXT
Inspect the current GTM and Customer Decision evidence contracts and add only owner-backed measurement mappings that preserve UNKNOWN for missing external outcomes.

WAIT
- Real GTM replies/WTP/payment/retention evidence.
- Canonical Customer Decision outcome semantics where still noncanonical.
- Canonical adoption / merge decision.

BLOCKERS
None for repository-safe synthetic measurement reconciliation.

EVIDENCE
- analytics/measurement-truth-registry@de1509f3bae21cdcc6763e676df45407c220849c before this BATON-only refresh.
- ObraSignal Quality run 33317537026: SUCCESS at that exact head.
- docs/DATA_ANALYTICS_CROSS_FACTORY_MEASUREMENT_v0.1.json on branch.

ASSUMPTIONS
- Missing evidence remains UNKNOWN.
- Synthetic fixtures never become external or customer proof.
- A metadata-only BATON update does not itself prove CI GREEN for the successor commit.

EXACT NEXT EXECUTABLE ACTION
Open GTM and Customer Decision owner evidence artifacts, map only evidence-backed observable fields into the Analytics contract, keep absent outcomes UNKNOWN, validate the updated JSON/Python tests, and classify the resulting exact-head CI.
