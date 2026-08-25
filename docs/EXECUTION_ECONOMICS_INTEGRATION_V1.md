# Execution Economics Integration v1

Status: integration candidate only. No queue promotion, production mutation, runtime activation or automatic merge is authorized by this contract.

## Purpose

`execution_economics.py` is a composition/read-model boundary over public owner contracts. It is intentionally not a second estimating, mobilization or economics engine.

Ownership remains:

- Bid Economics: commercial revenue/cost/margin, working-capital and guarantee economics.
- MOBILIZE: deterministic mobilization scenarios.
- BANGS: field observations, landed/field costs and execution-cost completeness.
- Company State (Q090): company resources, availability and financial constraints.
- Execution Economics: composition, uncertainty propagation, scope reconciliation and executive read model.

## Truth invariants

The composition never treats an unknown as zero or available. In particular:

- omitted lodging availability is `UNKNOWN`, not `AVAILABLE`;
- total employees are not available crew;
- owned vehicles are not available vehicles;
- provider failure is unavailable/error, never zero cost;
- observed price is not confirmed availability;
- list/observed price is not a quote or landed cost;
- known subtotal is not total cost while material unknowns remain;
- deposit is cash exposure, not economic cost;
- guarantee amount is not guarantee fee;
- opportunity/contract value is not revenue without an explicit Bid Economics revenue basis.

## Money

Owner monetary contracts remain authoritative. The composition exposes `MoneyView` only as a validated DTO:

- `Decimal` amount;
- explicit three-letter currency;
- no NaN/Infinity;
- no silent FX;
- no mixed-currency arithmetic.

When owner outputs contain more than one currency the assessment becomes `UNRESOLVED` and emits `MULTI_CURRENCY_UNRESOLVED` / `NO_FX_APPLIED`.

## Scope overlap

BANGS execution cost, MOBILIZE selected scenario cost and Bid Economics execution cost can overlap. The integration therefore does not sum them.

`ScopeReconciliation` records whether an external owner scope is already represented in Bid Economics. An omitted answer is unknown, not false. Until containment is explicit, the assessment carries scope blockers. Even after reconciliation, this composition does not manufacture a new combined profit; Bid Economics remains the sole owner of bid profit/margin calculations.

## Mobilization comparability

The read model exposes daily commute, accommodation and weekday-hybrid alternatives from MOBILIZE. A selected mobilization cost is suppressed at the integration boundary when any relevant alternative has unknown availability or is available but non-comparable because essential economics are missing. This prevents a known partial scenario from being presented as the cheapest defensible strategy while an essential alternative is unresolved.

## Company State

Only Q090 public adapters are consumed:

- `mobilize_inputs` for available crew, available own vehicles and base location;
- `economics_constraints` for cash/working-capital/guarantee limits;
- `bangs_inputs` for neutral field-intelligence seed facts.

The composition never reads private Q090 internals and never substitutes `crew.total_count` for `crew.available_count` or owned inventory for availability.

## Providers

BANGS provider statuses are projected as:

- `OK -> AVAILABLE`;
- `PROVIDER_UNAVAILABLE -> UNAVAILABLE`;
- timeout/rate-limit/invalid response -> `ERROR`.

An essential failed provider becomes a blocker. No provider failure creates an amount.

## Executive read model

`ExecutionEconomicsAssessment.read_model` exposes:

- KNOWN COSTS
- ESTIMATED COSTS
- ASSUMPTIONS
- UNKNOWN COSTS
- CASH EXPOSURE
- MOBILIZATION OPTIONS
- SOURCE/EVIDENCE BASIS
- WARNINGS
- BLOCKERS

This is a product data surface, not final Global UX visual design.

## What-if

`recompute_mobilization_what_if` supports only bounded deterministic MOBILIZE overrides:

- hotel rate;
- distance;
- crew size;
- working days;
- explicit hotel availability.

Overrides are labeled estimated/what-if evidence and delegated to the MOBILIZE owner. No AI forecast, Monte Carlo or arbitrary formula execution is introduced.

## Integration provenance

The integration candidate was assembled from public owner heads rather than copied/reimplemented internals:

- current main baseline used by Integration Lab;
- Integration Lab Bid Economics + BANGS combination;
- Q090 Company State public contracts;
- corrected MOBILIZE owner branch with Decimal money and tri-state availability.

Exact SHAs and CI evidence belong to the pull-request handoff and must be revalidated at every new candidate head.
