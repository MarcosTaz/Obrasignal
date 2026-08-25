# Opportunity Compare / Decision Matrix v0

## PURPOSE

Opportunity Compare is a small, deterministic, read-only capability for comparing 2–5 existing ObraSignal opportunities side by side. It reduces cognitive load by organizing facts and already-persisted account-specific assessments. It does not create a new ranking or recommendation.

## NON-GOALS

V0 does not choose a winner, predict win probability or margin, create custom weighted scores, perform portfolio optimization, execute bids, integrate MOBILIZE/UNLOCK/SHADOW, emit Value Created events, persist comparisons, or create an FX engine.

## INPUT CONTRACT

`compare_opportunities(conn, account_context, opportunity_ids, options=None)`

- `account_context` must contain the authenticated `account_id`; the production HTTP boundary derives it server-side and ignores any client-supplied `account_id`.
- `opportunity_ids` are current product-facing integer IDs from `tenders`.
- minimum: 2; maximum: 5.
- duplicates are rejected deterministically.
- malformed/non-positive IDs are rejected before SQL execution.
- `options.now` is an optional datetime intended for deterministic testing/internal callers.

The HTTP boundary is `POST /api/v1/opportunities/compare` with JSON `{ "opportunity_ids": [1, 2] }`.

## OUTPUT CONTRACT

The ephemeral response contains:

- `comparison_id` — deterministic identifier for account + ordered IDs + comparison version; it is not persisted.
- `comparison_version`.
- `generated_at`.
- `opportunities` — lightweight identifiers/titles only, not duplicated opportunity records.
- `dimensions` — the central dimension registry and semantics.
- `values_by_opportunity` — cells with `status`, `value`, `origin`, and `source`.
- `missing_data` — explicit missing dimension keys per opportunity.
- `data_completeness` — available/expected comparable fields and ratio; this is not confidence.
- `highlights` — deterministic observations only.
- `warnings` — e.g. mixed currencies.

## COMPARISON DIMENSIONS

V0 registers dimensions centrally in `COMPARISON_DIMENSIONS`:

| Key | Origin | Semantics |
| --- | --- | --- |
| `published_value` | FACT | Original known amount/value and currency; no FX conversion. |
| `deadline` | FACT | Canonical submission deadline. |
| `days_remaining` | DERIVED | Calendar-day difference from the normalized UTC comparison date. |
| `geography` | FACT | Canonical place/location/region/country when known. |
| `distance_km` | DERIVED | Existing account decision geography distance only; never newly calculated here. |
| `buyer` | FACT | Canonical buyer. |
| `work_type` | FACT | First known canonical work/procedure/category/CPV field. |
| `lots` | FACT | Existing canonical lot data only. |
| `qualification_requirements` | FACT | Existing canonical requirement data only. |
| `economic_fit` | DERIVED | Existing latest account-scoped `economic_fit`; never recalculated by Compare. |
| `capacity_fit` | DERIVED | Existing latest account-scoped capability evidence; never recalculated by Compare. |
| `opportunity_status` | FACT | Existing lifecycle/status value when available. |
| `decision_confidence` | DERIVED | Existing persisted decision confidence only. |
| `source_available` | DERIVED | Boolean derived from presence of canonical source/source-reference/URL metadata. |

Adding a dimension should require one registry entry and extractor rather than UI/controller conditionals.

## UNKNOWN SEMANTICS

Missing is not zero, false, poor, low, or rejected. A missing factual/assessment value is represented as:

`{"status": "UNKNOWN", "value": null, ...}`

A derived boolean such as `source_available=false` is a known derived result, not missing. `NOT_APPLICABLE` is reserved in the contract for future dimensions where absence is semantically inapplicable rather than unknown.

## DERIVED FIELDS

Derived fields are marked `DERIVED` at cell and registry level. V0 derives only simple comparison-safe values itself (`days_remaining`, source availability, deterministic highlights/completeness). Economic fit, capacity evidence, decision confidence, and known distance are reused from existing account decision output and remain explicitly labelled derived/system assessment rather than source facts.

Highlights are not recommendations. V0 may identify the nearest deadline, lowest known distance, highest published value within one currency, and the opportunity/opportunities with most missing comparison data.

## CURRENCY POLICY

No silent currency conversion. Original currencies are preserved. `highest_published_value` is emitted only when all parseable compared published values share one currency. Multiple currencies produce `MIXED_CURRENCIES` and no cross-currency value winner.

## ACCESS CONTROL

Current repository behavior treats `tenders` opportunities as globally readable product records. Compare follows that existing access model and does not introduce a separate opportunity ACL.

Private/account-specific decision data is selected only from the latest `opportunity_decisions` row scoped by the authenticated server-side `account_id`. The HTTP endpoint does not trust or consume a client-provided account ID. Parameterized SQL is used for opportunity IDs and account-scoped decision lookup.

If a future canonical Opportunity permission contract becomes more restrictive, Compare must consume that contract rather than inventing its own ACL.

## UI BEHAVIOR

V0 deliberately does not modify `mobile/App.js`. The current mobile surface is a compact monolithic Radar/detail implementation without a reusable multi-select pattern; adding a second selection state machine and comparison rendering in this parallel branch would increase UI blast radius and accessibility/regression risk beyond the isolated capability boundary.

The API contract is intentionally presentation-ready for a future minimal UI: select 2–5 Radar cards, disable selection at five with clear feedback, then render desktop-style columns or mobile cards/horizontal paging using `dimensions` + `values_by_opportunity`. UNKNOWN must remain visible and differences must not rely on color alone.

## TESTS

`tests/test_opportunity_compare.py` covers:

- 2 and 5 opportunities;
- rejection of 1 and >5;
- duplicate and malformed/injection-like IDs;
- missing opportunity;
- deterministic ordering/output;
- timezone-aware deadline and `days_remaining`;
- expired/closed/no-deadline/null-location cases;
- UNKNOWN/non-invention semantics;
- same- and mixed-currency behavior;
- very large values and different countries;
- explicit FACT vs DERIVED semantics;
- central registry uniqueness;
- account-scoped reuse of economic/capacity assessment;
- latest-decision selection and cross-tenant leakage prevention;
- read-only/no-mutation behavior.

## FUTURE EXTENSIONS

Not implemented in v0: Evidence Graph cell references, Watchlist `COMPARE SELECTED`, MOBILIZE cost dimensions, Opportunity Unlock, custom weighting, collaborative comparison, AI winner selection, exports, portfolio/sensitivity analysis, probability-of-win, or persistence/cache. Those require their own canonical contracts and future integration work.

## INTEGRATION / QUEUE SAFETY

This capability is prepared in parallel. It does not modify the canonical Master Execution Queue, change `CURRENT_ITEM_ID`, mark any queue capability DONE, claim production integration, or merge itself to `main`.
