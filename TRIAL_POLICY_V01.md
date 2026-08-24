# ObraSignal Pricing / Trial Policy v0.1

Status: **DECISION — VALIDATION REQUIRED**

## Commercial baseline

- Self-service / SME: **21-day ObraSignal Evaluation**.
- Enterprise: **30-day assisted pilot** with explicit objectives and success criteria.
- Free forever: no.
- Credit card before evaluation: no, initially.
- ObraSignal Evaluation is separate from any Google Play/App Store subscription trial.

## Activation

Account creation does not start the evaluation clock. New accounts move through onboarding until the minimum deterministic value-ready condition is met:

`profile_ready AND market_data_available AND first_relevant_shortlist_generated`

The activation event is persisted and auditable. The default evaluation lasts 21 days from activation.

## Extension

A controlled extension is at most 7 days and requires both real usage and insufficient value exposure caused by the product/data environment rather than simple user inactivity. No automatic or indefinite extension is permitted.

## Value exposure

Initial auditable event vocabulary:

- `profile_ready`
- `first_shortlist_generated`
- `relevant_opportunity_viewed`
- `deep_analysis_completed`
- `go_no_go_generated`
- `evidence_viewed`
- `alert_delivered`
- `action_taken`

Future events such as `unlock_used`, `mobilize_used`, and `supply_analysis_used` must not be emitted until those capabilities actually exist.

Exposure, engagement, measured value and estimated value are separate concepts. Counts of activity are facts; economic-value claims require a defined evidence-backed methodology.

## Metrics

Instrument/review: `TIME_TO_FIRST_VALUE`, `TRIAL_ACTIVATION_RATE`, `VALUE_EXPOSURE_RATE`, `DAY_1_ACTIVE`, `DAY_7_ACTIVE`, `DAY_14_ACTIVE`, `DAY_21_ACTIVE`, `TRIAL_TO_PAID`, `EXTENSION_RATE`, `EXTENSION_TO_PAID`, `CHURN_AFTER_CONVERSION`.

Review this baseline after 10 paying customers and again after 25 paying customers, or earlier if evidence clearly contradicts it.

## Precedence

Paid RevenueCat `pro` entitlement is independent of evaluation access and always wins while active. Existing accounts are not retroactively migrated from their legacy trial window without a separate explicit migration decision.
