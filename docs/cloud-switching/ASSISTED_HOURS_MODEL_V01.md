# Cloud Switching — Assisted Hours Model v0.1

Status: internal operating hypothesis. No customer willingness-to-pay or actual delivery time is proven yet.

## Objective

Measure whether the first paid `Verified Migration Economics Review` can be delivered as a standardized assisted product rather than linear bespoke consulting.

Primary anti-consulting metric:

`human_hours_per_verified_outcome`

Secondary metrics:

- `human_hours_per_baseline`
- `% evidence fields machine-ingested`
- `% evidence fields requiring manual reconciliation`
- `rework_hours_due_to_missing_or_incomparable_data`
- `customer_wait_days` separated from human labour hours

## Baseline Certification — target labour budget

| Work unit | Target hours | Fail/defer condition |
|---|---:|---|
| intake triage + case identity | 0.5 | no unique case/decision boundary |
| estate import/readiness review | 1.0 | stale/duplicate/UNKNOWN material estate |
| current-state billing normalization | 1.5 | material cost components UNKNOWN |
| status-quo / renewal economics | 1.0 | no documentary basis for renewal/status quo |
| alternative option normalization | 2.0 | fewer than two credible alternatives |
| migration-cost category reconciliation | 1.5 | transition categories omitted without explicit UNKNOWN |
| incentive ledger verification | 0.75 | potential/approved/received cannot be separated |
| forecast freeze + methodology/version check | 0.75 | original forecast cannot be frozen |
| QA / independent oracle check | 0.75 | oracle mismatch or unresolved arithmetic lineage |
| executive decision package | 0.75 | evidence insufficient for decision |
| **Target total** | **10.5 h** | |

Planning range: **8–14 human hours** for a qualified founding baseline.

At the current EUR 1,500 pricing hypothesis, 10.5 h implies EUR 142.86 revenue per human hour before overhead and a narrow service margin. Therefore EUR 1,500 should be treated as an acquisition/WTP test, not evidence of mature unit economics.

## Outcome Verification — target labour budget

| Work unit | Target hours |
|---|---:|
| actual evidence intake + provenance | 1.0 |
| post-migration billing normalization | 1.5 |
| migration invoices/labour/transition actuals | 1.5 |
| incentive receipt reconciliation | 0.5 |
| observation-window comparability | 1.0 |
| forecast→actual variance | 0.75 |
| downtime/performance evidence | 1.0 |
| benchmark eligibility/evidence grading | 0.75 |
| QA / independent oracle | 0.75 |
| final outcome report | 0.75 |
| **Target total** | **9.5 h** |

Planning range: **7–13 human hours**.

At the EUR 3,500 hypothesis and 9.5 h, revenue per human hour is EUR 368.42 before overhead.

## Lifecycle scenario

Baseline 10.5 h + one optional checkpoint 2.0 h + outcome 9.5 h = **22 h lifecycle labour**.

At EUR 6,000 lifecycle revenue hypothesis:

- revenue / human hour = EUR 272.73;
- if internal fully-loaded labour-equivalent cost is EUR 100/h, delivery labour cost = EUR 2,200;
- contribution before software/sales/admin = EUR 3,800, or 63.3%.

These are scenario calculations, not measured margins.

## Automation targets

The first 5 pilots may exceed these hour budgets. That is acceptable only if the excess produces reusable ingestion/methodology capability.

By outcome cohort:

- outcomes 1–5: measure every manual step; no target reduction claim;
- 6–10: target <18 lifecycle hours for standard VMware cohort;
- 11–20: target <14 lifecycle hours;
- 21–30: target <10 lifecycle hours;
- after 30: if standard cases remain >12 hours/outcome-equivalent, downgrade productization thesis.

`customer_wait_days` must never be counted as delivery labour.

## Hard kill/downgrade rules

Downgrade venture-scale thesis if after 20–30 comparable outcomes:

1. median lifecycle human hours remain >12 without a clear automated ingestion path;
2. >40% of material evidence fields still need custom manual interpretation;
3. each new customer requires bespoke schema/methodology changes;
4. evidence collection consumes more human time than economic analysis;
5. independent verification routinely depends on executor/provider narrative rather than authoritative sources.

A high-priced consulting service can still be viable if these fail, but the data/product scaling thesis is weakened.

## Instrumentation requirement

Every assisted case should record labour by standardized activity code, not a single total:

`INTAKE, ESTATE, BILLING, STATUS_QUO, OPTIONS, MIGRATION_COST, INCENTIVE, FORECAST_FREEZE, COMPARABILITY, ACTUALS, PERFORMANCE, ORACLE_QA, REPORT, REWORK`.

The product should later compute hours by case/cohort and identify the steps to automate first.
