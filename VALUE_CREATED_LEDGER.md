# ObraSignal Value Created Ledger v0

## Purpose

Provide a small, passive, auditable ledger that can answer: **what economic value did ObraSignal help this account create, preserve, recover, or avoid?** The ledger records evidence-backed observations; it does not discover value autonomously and does not generate marketing claims.

Contract version: `value-created-ledger.v0`.

## Non-goals

V0 does not implement a ROI dashboard, billing/value pricing, commissions, transaction fees, FX conversion, accounting integrations, causal inference/ML, benchmarks, automatic marketing statements, or connectors. It does not replace Evidence Graph, Outcome Graph, Decision Ledger, MOBILIZE, SUPPLY EDGE, OFFICE, SHADOW, COMMAND, or ACTION.

## Domain contract

Primary functions:

- `record_value_event(conn, ...) -> ValueEvent`
- `get_value_event(conn, account_id=..., event_id=...) -> ValueEvent | None`
- `get_value_summary(conn, account_id=..., start_at=..., end_at=...) -> ValueSummary`
- `ensure_value_ledger_schema(conn)` for the existing SQLite persistence model.

The API is intentionally internal for V0. No public HTTP endpoint is added while canonical item `Q230_VALUE_CREATED` remains gated.

## Value types

`MEASURED` means an economic outcome directly demonstrated by observed facts. `ESTIMATED` means a calculated value using an explicit, traceable method. `QUALIFIED` is potential opportunity value and is **not** value created. `UNKNOWN` means the event is economically relevant but no defensible numeric value is available.

These buckets are never combined into one total. `UNKNOWN` cannot carry a numeric amount in V0.

## Event fields

`ValueEvent` retains tenant, category, value type, amount, currency/unit, occurrence/recording timestamps, source, optional decision/opportunity/project references, method, confidence, evidence references, assumptions, notes, status, deduplication key, causal reference, and correction/supersession links.

References are intentionally shallow: the ledger does not duplicate company profiles, opportunities, projects, decisions, or evidence documents. A numeric event is either monetary (`currency`) or non-monetary (`unit`), never both.

## Categories in v0

The contract accepts this conservative initial set:

- `qualified_opportunity`
- `bad_bid_avoided`
- `mobilization_saving`
- `sourcing_saving`
- `margin_preserved`
- `time_saved`
- `idle_capacity_recovered`
- `contractual_value_protected`
- `financing_cost_avoided`
- `operational_cost_reduction`

A category being accepted by the ledger does not mean the corresponding producer capability is active.

## Measured vs estimated

An estimated numeric event with an amount must include `method`. For example, a MOBILIZE scenario delta can be recorded as `ESTIMATED` while unexecuted. If an actual outcome is later observed, a separate `MEASURED` event is appended. The original estimate remains intact for future calibration.

Negative values are valid. A recommendation that was expected to create `+EUR 5,000` but later caused `-EUR 1,000` can retain both events. The ledger must not be structurally biased toward positive outcomes.

Measured and estimated values remain separate for both monetary and non-monetary quantities. Time and other units are never combined across these value types in top-level summaries.

## Status and confidence

Statuses are `PROPOSED`, `OBSERVED`, `VERIFIED`, `REJECTED`, and `SUPERSEDED`. Numeric summaries include only `OBSERVED` and `VERIFIED` events. Unknown events default to `PROPOSED`; the system does not automatically upgrade estimates to `VERIFIED`.

Confidence is deliberately coarse: `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`. V0 does not invent confidence percentages.

## Currency

Money is stored as decimal text and aggregated by currency. `EUR 1,000` and `USD 1,000` remain separate. V0 has no FX engine and therefore never reports them as `2,000` of an unspecified currency.

## Time saved

Time can be recorded without money, e.g. `3 hours`. Measured and estimated time are exposed in separate summary buckets. If time is converted to money, the monetary observation must be a separately defensible `ESTIMATED` event with a method such as an explicit hourly-value assumption.

## Qualified opportunity value

A contract value discovered by ObraSignal is not automatically value created. `qualified_opportunity` accepts only `QUALIFIED` or `UNKNOWN` value types. A numeric `QUALIFIED` event must be a monetary amount with a currency; non-monetary qualified quantities are rejected. `UNKNOWN` is used when no defensible numeric opportunity value exists. This prevents a EUR 900,000 tender from becoming a false EUR 900,000 value-created claim while keeping qualified pipeline value separately reportable.

## Immutability, correction, and lifecycle

`record_value_event` is append-only. It contains no update path. Corrections use `corrects_event_id`; replacement semantics can use `supersedes_event_id`. The historical target remains stored. Current summaries exclude a corrected/superseded target when the replacement is in the reporting set.

Correction/supersession references are tenant-scoped and cannot point at another account. Period summaries intentionally evaluate replacement semantics within the selected reporting set; a later correction outside that period does not silently rewrite the historical window.

## Duplicate and double-counting controls

`deduplication_key` is unique per account and rejects a producer-level duplicate. Duplicate `event_id` values are reported separately from deduplication-key collisions.

`causal_reference` identifies the same underlying economic benefit across labels or modules. Summary aggregation counts a causal benefit once per value type + currency/unit. This permits an estimate and later measured outcome to coexist, while preventing a known EUR 3,000 mobilization saving and the same EUR 3,000 margin-preserved effect from becoming EUR 6,000.

If active observations use the same causal reference/value type/dimension but disagree on the amount, summary generation fails closed. The producer must reconcile the conflict with an explicit correction or supersession; row order never chooses the economic value.

This is intentionally conservative. V0 does not attempt automatic causal inference when no causal reference is supplied.

## Tenant isolation

Every persisted event has a mandatory `account_id`. Reads and summaries require the account explicitly. Correction/supersession links are validated against account ownership. The ledger has no cross-tenant summary operation.

## Summary contract

`ValueSummary` exposes, separately:

- measured monetary value by currency;
- estimated monetary value by currency;
- qualified opportunity value by currency;
- measured time saved by unit;
- estimated time saved by unit;
- measured other non-monetary value by category/unit;
- estimated other non-monetary value by category/unit;
- deterministic category/value-type/currency-or-unit breakdown.

It supports optional UTC-aware period filtering by `occurred_at`.

## Examples

### Example A — measured saving

Supplier invoice baseline: EUR 10,000. Actual negotiated invoice: EUR 8,800. Record `MEASURED EUR 1,200`, with source/evidence references sufficient to defend the comparison.

### Example B — estimate only

MOBILIZE predicts EUR 4,300 saving but no scenario has been executed. Record `ESTIMATED EUR 4,300` with method `mobilization_scenario_difference_v1`. Do not later overwrite it; append the actual as `MEASURED` if one becomes known.

### Example C — opportunity

ObraSignal identifies a EUR 900,000 opportunity. Record `QUALIFIED EUR 900,000` under `qualified_opportunity`. Value created remains unknown unless a separate defensible value event exists.

### Example D — time

Tender review previously took 5 hours and the assisted process took 2 hours. Record `MEASURED 3 hours` under `time_saved`. Financial value remains unknown unless a separate explicit conversion method is supplied.

## Integration contract

Future producers such as MOBILIZE, SUPPLY EDGE, COMMAND, OUTCOME, or manual confirmation may call `record_value_event` from application/domain code. `source` is intentionally an auditable string rather than evidence that a source capability is active. `decision_id`, `opportunity_id`, `project_id`, and `evidence_refs` are references only.

For MOBILIZE, an unexecuted probable-cost delta is `ESTIMATED`; a later invoice/actual comparison may be appended as `MEASURED`. For Outcome Graph, predicted and actual events should share a causal reference where they represent the same economic outcome, without deleting either observation.

## Known limitations

V0 does not validate that referenced decision/opportunity/project/evidence IDs exist because the richer canonical ledgers are not yet production contracts. It also cannot detect double counting when producers fail to provide a deduplication or causal reference. Manual confirmation is representable by `source="MANUAL_CONFIRMATION"` but is not treated as external audit merely because of that label. There is no FX conversion or automatic policy for reconciling conflicting causal amounts.

## Future

After canonical Q230 is explicitly ungated, safe next work may include capability-registry wiring, authenticated internal/API adapters, Outcome Graph integration, evidence-reference validation, richer correction semantics, and calibrated producer-specific methods. None of those are implied to be active by this V0.

**Prepared in parallel. Does not modify canonical execution order or promote the Value Created capability to production.**