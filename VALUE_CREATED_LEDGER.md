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

These buckets are never combined into one total. This applies to money **and** non-monetary quantities such as hours or crew-days.

`UNKNOWN` cannot carry a numeric amount. If a numeric value is defensible enough to store, it must be classified explicitly as `MEASURED`, `ESTIMATED`, or `QUALIFIED` where allowed.

## Event fields

`ValueEvent` retains tenant, category, value type, amount, currency/unit, occurrence/recording timestamps, source, optional decision/opportunity/project references, method, confidence, evidence references, assumptions, notes, status, deduplication key, causal reference, and correction/supersession links.

A numeric event is either monetary (`currency`) or non-monetary (`unit`), never both in the same event. This prevents ambiguous quantities such as a single amount being interpreted simultaneously as EUR and hours.

References are intentionally shallow: the ledger does not duplicate company profiles, opportunities, projects, decisions, or evidence documents.

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

An estimated event with a numeric amount must include `method`, whether the amount is monetary or non-monetary. For example, a MOBILIZE scenario delta can be recorded as `ESTIMATED` while unexecuted. If an actual outcome is later observed, a separate `MEASURED` event is appended. The original estimate remains intact for future calibration.

Negative values are valid. A recommendation that was expected to create `+EUR 5,000` but later caused `-EUR 1,000` can retain both events. The ledger must not be structurally biased toward positive outcomes.

## Status and confidence

Statuses are `PROPOSED`, `OBSERVED`, `VERIFIED`, `REJECTED`, and `SUPERSEDED`. Numeric summaries include only `OBSERVED` and `VERIFIED` events. Unknown events default to `PROPOSED`; the system does not automatically upgrade estimates to `VERIFIED`.

Confidence is deliberately coarse: `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`. V0 does not invent confidence percentages.

## Currency

Money is stored as decimal text and aggregated by currency. `EUR 1,000` and `USD 1,000` remain separate. V0 has no FX engine and therefore never reports them as `2,000` of an unspecified currency.

## Time saved and other non-monetary value

Time can be recorded without money, e.g. `3 hours`. Measured time and estimated time are separate summary buckets. They are never added together.

The same rule applies to other non-monetary quantities such as `crew_days`: measured quantities and estimated quantities are reported separately.

If time is converted to money, the monetary observation must be a separate defensible `ESTIMATED` event with an explicit conversion method such as an hourly-value assumption. The original time event remains non-monetary.

## Qualified opportunity value

A contract value discovered by ObraSignal is not automatically value created. `qualified_opportunity` accepts only `QUALIFIED` or `UNKNOWN` value types. This prevents a EUR 900,000 tender from becoming a false EUR 900,000 value-created claim.

## Immutability, correction, and lifecycle

`record_value_event` is append-only. It contains no update path. Corrections use `corrects_event_id`; replacement semantics can use `supersedes_event_id`. The historical target remains stored. Current summaries exclude a corrected/superseded target when the replacement is in the reporting set.

Correction/supersession references are tenant-scoped and cannot point at another account.

## Duplicate and double-counting controls

`deduplication_key` is unique per account and rejects an exact producer-level duplicate.

`causal_reference` identifies the same underlying economic benefit across labels or modules. Summary aggregation counts a causal benefit once per value type + currency/unit. This permits an estimate and later measured outcome to coexist, while preventing a known EUR 3,000 mobilization saving and the same EUR 3,000 margin-preserved effect from becoming EUR 6,000.

If two active observations claim the same causal benefit, value type and dimension but disagree on the amount, summary generation **fails closed**. The ledger does not choose one amount based on row order; a producer must reconcile the conflict with an explicit correction or supersession event.

This is intentionally conservative. V0 does not attempt automatic causal inference when no causal reference is supplied.

## Tenant isolation

Every persisted event has a mandatory `account_id`. Reads and summaries require the account explicitly. Correction/supersession links are validated against account ownership. The ledger has no cross-tenant summary operation.

## Summary contract

`ValueSummary` exposes, separately:

- measured monetary value by currency;
- estimated monetary value by currency;
- qualified opportunity value by currency;
- measured time saved by unit (`time_saved_by_unit`);
- estimated time saved by unit (`estimated_time_saved_by_unit`);
- measured other non-monetary value by category/unit (`other_non_monetary`);
- estimated other non-monetary value by category/unit (`estimated_other_non_monetary`);
- deterministic category/value-type/currency-or-unit breakdown.

No top-level summary bucket combines `MEASURED` and `ESTIMATED` quantities.

It supports optional UTC-aware period filtering by `occurred_at`. Correction/supersession replacement semantics are evaluated within the selected reporting set; V0 does not silently rewrite historical windows using later out-of-window events.

## Examples

### Example A — measured saving

Supplier invoice baseline: EUR 10,000. Actual negotiated invoice: EUR 8,800. Record `MEASURED EUR 1,200`, with source/evidence references sufficient to defend the comparison.

### Example B — estimate only

MOBILIZE predicts EUR 4,300 saving but no scenario has been executed. Record `ESTIMATED EUR 4,300` with method `mobilization_scenario_difference_v1`. Do not later overwrite it; append the actual as `MEASURED` if one becomes known.

### Example C — opportunity

ObraSignal identifies a EUR 900,000 opportunity. Record `QUALIFIED EUR 900,000` under `qualified_opportunity`. Value created remains unknown unless a separate defensible value event exists.

### Example D — measured vs estimated time

Tender review previously took 5 hours and the assisted process took 2 hours. Record `MEASURED 3 hours` under `time_saved`.

A future workflow might separately predict `ESTIMATED 4 hours` saved using `method="workflow_baseline_v1"`. The summary exposes `3 measured hours` and `4 estimated hours`; it never reports `7 hours saved`.

## Integration contract

Future producers such as MOBILIZE, SUPPLY EDGE, COMMAND, OUTCOME, or manual confirmation may call `record_value_event` from application/domain code. `source` is intentionally an auditable string rather than evidence that a source capability is active. `decision_id`, `opportunity_id`, `project_id`, and `evidence_refs` are references only.

For MOBILIZE, an unexecuted probable-cost delta is `ESTIMATED`; a later invoice/actual comparison may be appended as `MEASURED`. For Outcome Graph, predicted and actual events should share a causal reference where they represent the same economic outcome, without deleting either observation.

## Known limitations

V0 does not validate that referenced decision/opportunity/project/evidence IDs exist because the richer canonical ledgers are not yet production contracts. It also cannot detect double counting when producers fail to provide a deduplication or causal reference. Manual confirmation is representable by `source="MANUAL_CONFIRMATION"` but is not treated as external audit merely because of that label.

V0 intentionally has no FX conversion and no automatic reconciliation policy for conflicting causal amounts. Conflicts must be corrected explicitly so the audit trail remains visible.

## Future

After canonical Q230 is explicitly ungated, safe next work may include capability-registry wiring, authenticated internal/API adapters, Outcome Graph integration, evidence-reference validation, richer correction semantics, and calibrated producer-specific methods. None of those are implied to be active by this V0.

**Prepared in parallel. Does not modify canonical execution order or promote the Value Created capability to production.**