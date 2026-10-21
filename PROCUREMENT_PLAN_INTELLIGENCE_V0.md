# ObraSignal Procurement Plan Intelligence v0

## PURPOSE
Turn formally published future procurement intent into conservative, provenance-first decision signals before a live tender exists.

## NON-GOALS
This module does not predict Future Demand, calculate probability of procurement/win, prepare bids, discover contacts, send outreach, or promote Q030. It does not claim global procurement-plan coverage.

## PLAN VS TENDER
`PROCUREMENT_PLAN`, `FORECAST`, `PRIOR_INFORMATION`, related `CAPITAL_PROJECT` and `MARKET_DIALOGUE` signals remain pre-tender signals. They never acquire a bid deadline or `Submit bid` CTA merely because they describe future work. A plan is intent; it can change, defer, cancel or never become a tender.

## SIGNAL TYPES
The canonical Signal store already supports `PROCUREMENT_PLAN`, `FORECAST`, `CAPITAL_PROJECT` and `MARKET_DIALOGUE`. v0 also recognizes `PRIOR_INFORMATION` at the planning intelligence boundary; canonical Signal persistence must explicitly admit that type before a connector persists it there. This branch intentionally does not mutate the existing Signal contract to avoid an unreviewed cross-cutting contract change.

## DATE SEMANTICS
Planning dates are represented as `EXACT`, `MONTH`, `QUARTER`, `YEAR`, `RANGE`, `WINDOW`, or `UNKNOWN`. `Q2 2027` remains a quarter and is never silently converted into 2027-04-01. Legacy `target_date` is interpreted as a future-need date for plan signals, never as a tender deadline. Published/update timestamps are separate from planned procurement timing.

## VALUE SEMANTICS
Plan values are always `ESTIMATED`. Single estimates and min/max ranges are supported. Currency is explicit and no FX conversion occurs. Estimated plan value is not award value, contract value, or proof of approved budget.

## STATUS MODEL
`PLANNED`, `PUBLISHED`, `UPDATED`, `DEFERRED`, `CANCELLED`, `SUPERSEDED`, `UNKNOWN`. Cancelled/deferred/superseded records remain historical but are not active future procurement. Source health degradation is not interpreted as cancellation.

## IDENTITY
Canonical identity is `source + signal_type + external_id`. Adapters should make `external_id` publisher-native: official plan item ID, procurement reference, OCID/item identity, or a defensible stable composite. Titles are never identity.

## VERSIONING
The read model emits a deterministic normalized fingerprint and preserves optional revision/source update timestamps. Existing `signal_records` storage already upserts on `(source, signal_type, external_id)`, preserving first/last observation; repeated ingestion therefore remains one logical canonical record. Full immutable revision history is intentionally not duplicated here.

## LINEAGE
Plan→tender matching is conservative. v0 requires an explicit/shared official reference (source reference, plan reference or OCID). Same buyer + similar title/value is insufficient. A linked plan remains history rather than disappearing when the tender is published. The hook has no hard dependency on a future lineage implementation.

## SOURCE-SPECIFIC NORMALIZATION
Core planning intelligence contains no `if source == Brazil/UK/Canada` branches. Source adapters remain responsible for native IDs and source-specific semantics. A pre-existing Brazil PNCP PCA implementation exists on a gated branch and already emits `PROCUREMENT_PLAN`; this module can consume its normalized records without promoting that connector or changing the Master Queue.

## CONFIDENCE
Confidence describes signal evidence/semantic quality, not probability the tender will happen or a contractor will win. The default policy is conservative: official reference + exact date + value may be HIGH; official reference + approximate timing MEDIUM; weaker structured evidence LOW; insufficient semantics UNKNOWN.

## API / UI
v0 exposes a pure `plan_read_model()` suitable for an API/UI integration. It labels the entity `Planned procurement`, reports precision and estimated-value semantics, sets `deadline=None`, `is_open_tender=False`, and uses `View source`, not `Submit bid`. No new public route is added because the current API is tender/workflow-centric and a separate endpoint would require persistence/query integration beyond the isolated read-model contract.

## TESTS
Dedicated tests cover exact/month/quarter/year/range/window/unknown dates; no false precision; estimated values/ranges/currencies; planned/updated/deferred/cancelled lifecycle; deterministic identity/fingerprint; buyer/location/provenance/budget; conservative lineage; legacy target-date semantics; false tender/commitment/value controls; malformed input and text bounds.

## SECURITY
Normalization is pure: no SQL, HTML rendering, network calls, authentication or tenant data. Text is bounded, currencies/dates are validated, runtime-private keys are excluded from fingerprint input, and no private annotation storage is introduced. UI consumers must continue escaping text using their framework conventions.

## KNOWN LIMITATIONS
No production connector is promoted by this branch. No immutable change-history table is added. Buyer identity uses a supplied canonical `buyer_id` when available but does not create a competing buyer resolver. Category/location are preserved from normalized input rather than reclassified. Partial dates intentionally do not support day-count lead time.

## FUTURE DEMAND INTEGRATION
Formal plan signals are strong future inputs to Future Demand, but this capability performs no predictive inference. `PLANNED PROCUREMENT != DEMAND CERTAINTY` remains a hard boundary.

## ROLLBACK
The branch adds one pure Python module, one test module and this document. Rollback is deletion of those files; there is no migration or data rewrite.

Prepared in parallel. Does not modify the canonical Master Execution Queue, implement predictive Future Demand, or claim production procurement-plan coverage.
