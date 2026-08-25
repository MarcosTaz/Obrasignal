# ObraSignal MOBILIZE v1

Status: **isolated implementation / gated capability**. This module does not promote canonical queue item `Q222_MOBILIZE_RESEARCH`, enable production behavior, call external vendors, or create a parallel Decision Ledger.

## Purpose

MOBILIZE answers:

> Qual é a forma economicamente mais racional de mobilizar esta equipa e estes recursos para esta obra?

V1 compares six deterministic configurations formed from three work patterns and two vehicle modes:

- `DAILY_COMMUTE` + `OWN`
- `DAILY_COMMUTE` + `RENTAL`
- `ACCOMMODATION` + `OWN`
- `ACCOMMODATION` + `RENTAL`
- `WEEKDAY_HYBRID` + `OWN`
- `WEEKDAY_HYBRID` + `RENTAL`

It evaluates direct mobilization cost plus, when supplied by company/regional policy, the economic value of non-productive crew travel. Cost intervals and operational travel exposure remain separately auditable.

## Stable contract

```python
from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput

assessment = Mobilize.evaluate(context, policy)
```

The output is `MobilizationAssessment` (`contract_version="mobilize.v1"`) with:

- `recommended_scenario`
- ranked `alternative_scenarios`
- `estimated_cost`, `minimum_cost`, `probable_cost`, `prudent_cost`
- `cost_per_worker`, `cost_per_day`
- `travel_hours`, `non_productive_hours`
- `productivity_impact`
- `operational_risks`
- `assumptions`, `missing_inputs`
- `confidence`
- `evidence`
- `warnings`

`to_dict()` provides a serialization-friendly representation without coupling consumers to storage or HTTP.

## Inputs

`MobilizationContext` owns only the project/crew facts needed by the engine:

- worker count and working days;
- one-way route distance and optional one-way travel time;
- workdays/week;
- seats/vehicle and optional own-vehicle availability;
- rental/accommodation availability;
- optional local transport distance while staying near site;
- currency.

`MobilizePolicy` owns company/regional economics and decision thresholds:

- fuel price;
- own/rental vehicle consumption;
- own-vehicle wear/depreciation cost per km;
- rental daily rate;
- tolls and parking;
- accommodation;
- per diem;
- productive-hour value;
- optional maximum daily travel/fatigue-risk thresholds;
- `near_cost_ratio` for the maximum policy-approved premium over the cheapest probable scenario;
- `material_travel_reduction_hours` for the minimum crew-hours reduction required before travel exposure can break an overlapping-cost tie;
- explicit policy version.

The policy defaults `near_cost_ratio` to `1.10` and `material_travel_reduction_hours` to `1.0`. They are explicit, validated, replaceable policy defaults — not universal economic facts.

There are no live-price defaults. Unknown economic inputs remain `UNKNOWN`. A caller that knows a cost is zero should supply an explicit zero-valued `RangeInput`.

## Uncertainty and provenance

Every route/economic input is a `RangeInput` carrying `minimum`, `probable`, `prudent`, source metadata and one of:

- `LIVE`
- `QUOTED`
- `RECENT`
- `ESTIMATED`
- `UNKNOWN`

Output evidence projects inputs to `KNOWN`, `ESTIMATED`, `ASSUMED`, or `UNKNOWN`.

The contract rejects:

- partial ranges;
- negative values;
- `NaN` or infinite values;
- unsupported evidence-quality labels;
- values marked `UNKNOWN` while simultaneously supplying a number.

This prevents malformed inputs from entering ranking or confidence logic.

Unknown components remain visible in `missing_inputs`, reduce confidence, and generate warnings. A scenario becomes non-comparable when an economically essential component is unknown. In V1, that includes:

- route distance;
- non-zero-distance fuel price;
- non-zero-distance consumption for the selected vehicle mode;
- own-vehicle cost/km for non-zero-distance own-vehicle scenarios;
- rental price for rental scenarios;
- accommodation price for stay scenarios.

Tolls, parking, per diem, travel time and productive-hour value can remain unknown without crashing the engine, but are explicitly excluded from the reported cost and confidence is degraded. Consumers must not present such outputs as fully-loaded actual cost.

For a true zero-distance project, propulsion and own-vehicle km costs are not required to compare the zero-distance commute because the underlying distance-driven quantity is zero.

## Scenario mechanics

### Daily commute

One base/site round trip per working day. Vehicle km, fuel, wear/rental, tolls, parking and crew travel hours are calculated over the project.

### Weekday hybrid

Workdays are grouped by `working_days_per_week`. The model uses one base/site round trip per working week and `days in group - 1` lodging nights, covering patterns such as Monday travel / Friday return.

### Continuous accommodation

The crew makes one base/site round trip. V1 infers the calendar span from working days and workdays/week and treats the crew as continuously lodged between first and last workday. This intentionally differs from weekday hybrid.

### Vehicle modes

`OWN` adds fuel plus explicit own-vehicle cost/km. `RENTAL` adds fuel plus rental-day cost. V1 models rental on the same base/site travel pattern; local-only pickup plus separate crew transfer is a future extension and is disclosed as an assumption.

## Recommendation rule

MOBILIZE does **not** blindly select the smallest displayed cash number.

1. unavailable or non-comparable scenarios cannot win;
2. probable installed economic cost ranks viable scenarios;
3. where leading uncertainty intervals overlap, simple cost ordering is treated as weak;
4. when travel exposure is known, a lower-travel scenario may break the tie only when both policy conditions are met:
   - its probable cost is within `near_cost_ratio` of the cheapest probable scenario; and
   - it reduces crew travel by at least `material_travel_reduction_hours`;
5. otherwise materially overlapping leading ranges return `NO CLEAR WINNER`.

Configured fatigue and maximum-travel thresholds add operational risks. There is no universal hard-coded fatigue percentage.

## Confidence

Confidence is deterministic and auditable. It starts at 100 for a comparable scenario and is reduced for lower evidence quality, missing inputs and explicit model assumptions. A non-comparable scenario has confidence 0. It is not an AI confidence score and does not substitute for the evidence list.

## Example

```python
ctx = MobilizationContext(
    workers=10,
    working_days=60,
    distance_km_one_way=RangeInput.scalar(
        130, quality="QUOTED", source="approved route estimate"
    ),
    travel_hours_one_way=RangeInput(
        1.5, 1.7, 2.0, quality="RECENT", source="route study"
    ),
    own_vehicles_available=2,
    currency="EUR",
)

policy = MobilizePolicy(
    currency="EUR",
    fuel_price_per_litre=RangeInput(
        1.70, 1.80, 1.95, quality="RECENT", source="regional policy"
    ),
    own_vehicle_consumption_l_per_100km=RangeInput.scalar(
        8.5, quality="QUOTED", source="fleet record"
    ),
    own_vehicle_cost_per_km=RangeInput(
        0.10, 0.14, 0.20, quality="ESTIMATED", source="fleet policy"
    ),
    rental_vehicle_daily_cost=RangeInput(
        65, 75, 90, quality="QUOTED", source="rental quote range"
    ),
    rental_vehicle_consumption_l_per_100km=RangeInput.scalar(
        8.0, quality="ESTIMATED", source="vehicle class estimate"
    ),
    tolls_per_vehicle_round_trip=RangeInput.scalar(
        20, quality="QUOTED", source="route estimate"
    ),
    parking_per_vehicle_workday=RangeInput.scalar(
        0, quality="QUOTED", source="site condition"
    ),
    accommodation_per_worker_night=RangeInput(
        30, 40, 55, quality="QUOTED", source="lodging quote range"
    ),
    per_diem_per_worker_day=RangeInput.scalar(
        15, quality="ESTIMATED", source="company policy"
    ),
    productive_hour_value_per_worker=RangeInput(
        15, 20, 25, quality="ESTIMATED", source="company economics"
    ),
    fatigue_risk_travel_hours=2.5,
    near_cost_ratio=1.08,
    material_travel_reduction_hours=10,
)

assessment = Mobilize.evaluate(ctx, policy)
```

These numbers are illustrative inputs, not Portugal or global defaults.

## Integration boundaries

- **OFFICE / Capacity:** future adapters provide crew/capacity facts. MOBILIZE does not own workforce master data.
- **SIGNAL / Opportunity / Project:** future adapters map canonical project/location facts into `MobilizationContext`. MOBILIZE does not duplicate opportunity persistence.
- **SHADOW / COMMAND:** consume `MobilizationAssessment` through `mobilize.v1`; do not read module internals.
- **Evidence Graph:** evidence, assumptions, `policy_version`, `contract_version` and deterministic replay inputs are ready to project into the future evidence/decision-ledger contract.
- **SITE READY:** MOBILIZE answers how to get people/resources there economically; SITE READY owns pre-start blockers.
- **Supply Edge:** materials and procurement remain outside MOBILIZE.

No existing Core schema is changed by V1. No endpoint or UI is added because the repository architecture does not require one to validate the pure engine.

## Known limitations / FUTURE

V1 intentionally does not provide:

- route, traffic, hotel, rental or fuel APIs;
- tax or employment-law calculations;
- local temporary labour or subcontract comparison;
- local-only rental pickup with a separate crew-transfer mode;
- fleet opportunity-cost optimization;
- advanced fatigue/safety models;
- equipment/material logistics;
- live booking or external actions;
- a standalone Decision Ledger;
- UI or HTTP endpoint.

Travel time for local site transport is not modeled separately. Availability is an explicit caller fact, not inferred from the market.

## Testing

The MOBILIZE tests cover commute/accommodation/hybrid economics, own-vs-rental, zero distance, single and large crews, equal-cost ambiguity, duration and worker scaling invariants, extreme durations, missing/unknown values, invalid and non-finite inputs, evidence-quality validation, deterministic output, confidence degradation, uncertainty propagation, availability, currency validation, ranking stability, policy-driven fatigue risk and policy-driven tie-breaking thresholds.

The engine depends only on the Python standard library.
