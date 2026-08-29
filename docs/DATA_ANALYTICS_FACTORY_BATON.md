# Data, Analytics & Learning System Factory — BATON

STATUS: ACTIVE / REPOSITORY_ONLY / NOT_CANONICAL

MISSION: measure product, operational and commercial learning without converting missing evidence into zeros, rejection, success, or false precision.

VERSION / HEAD BEFORE BATON: 37b52f855b88a08e796375f717f3eff2187ed4ad
BRANCH: analytics/measurement-truth-registry

CURRENT TRUTH
- Commercial funnel logic explicitly keeps missing or partial owner evidence UNKNOWN.
- Adjacent OBSERVABLE owner counts may compute progression/dropoff rates.
- PARTIAL/UNKNOWN evidence cannot publish a numeric count.
- Zero denominator cannot manufacture a rate.
- Non-monotonic owner counts are exposed as inconsistent.
- Unknown commercial stages fail closed.
- Exact-head ObraSignal Quality runs 32891212362 and 32890049116 are SUCCESS.

ACTIVE
Create a cross-factory measurement handoff that can consume GTM and Customer Decision evidence without inferring replies, interest, payment, retention, decision quality or outcome quality from absence of records.

NEXT
Add a synthetic measurement contract for evidence ownership, observation timestamp, quality, numerator/denominator authority and canonical status. Include negative cases for missing owner evidence, stale observation, non-monotonic counts, unknown outcome and synthetic-only evidence.

WAIT
- Real GTM replies/WTP/payment/retention evidence.
- Canonical Customer Decision outcome semantics where still noncanonical.
- Canonical adoption / merge decision.

BLOCKERS
None for repository-safe synthetic measurement work.

EVIDENCE
- analytics/measurement-truth-registry@37b52f855b88a08e796375f717f3eff2187ed4ad.
- ObraSignal Quality 32891212362 SUCCESS.
- ObraSignal Quality 32890049116 SUCCESS.

ASSUMPTIONS
- Missing evidence remains UNKNOWN.
- Synthetic fixtures never become external or customer proof.

EXACT NEXT EXECUTABLE ACTION
Add docs/DATA_ANALYTICS_CROSS_FACTORY_MEASUREMENT_v0.1.json and keep all absent external outcomes UNKNOWN; then classify the exact new HEAD from CI if CI exists.
