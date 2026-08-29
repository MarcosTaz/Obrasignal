# Cloud Switching — Founding Pilot Acceptance v0.1

Status: pilot operating contract hypothesis. Not legal terms and not external WTP evidence.

## Pilot objective

Produce one auditable independent decision record before migration and one comparable outcome record after migration without rewriting the original promise.

A pilot is not considered accepted merely because the software runs. It must produce a decision package whose material inputs are evidence-linked and whose unknowns are explicit.

## Entry gate

A case can enter Baseline Certification only if all are true:

1. one decision boundary/case ID is identifiable;
2. current infrastructure estate passes decision-readiness checks;
3. at least one status-quo/renewal option and one credible change option exist;
4. material current-state cost components are available or explicitly classified UNKNOWN;
5. migration cost categories can be represented without silent omission;
6. provider/partner incentives can be separated into potential/approved/received;
7. the pre-decision forecast can be frozen and versioned;
8. customer permits authoritative evidence to be used for the review.

If a material item is UNKNOWN, the system may return `NEEDS_MORE_EVIDENCE` rather than force a recommendation.

## Baseline Certification acceptance

Required output sections:

- case identity and decision date;
- estate summary and readiness result;
- source/evidence register;
- current-state annual cost;
- status-quo/renewal economics;
- compared options with same currency/horizon;
- migration investment categories;
- provider/partner incentives, separately disclosed;
- economic winner vs customer-cash winner;
- frozen forecast: cost, duration, run-rate, downtime, incentives;
- economic payback and cash payback where denominators are positive;
- decision: `SWITCH / DO_NOT_SWITCH_NOW / RENEW_TEMPORARILY / NEEDS_MORE_EVIDENCE`;
- evidence-strength and comparability warnings;
- methodology version and package content hash.

A Baseline Certification FAILS if:

- the estate is materially stale/incomplete;
- baseline does not reconcile to the decision case;
- fewer than two credible options are compared where a switch decision is claimed;
- migration investment excludes a known material category;
- incentives are netted into savings;
- forecast cannot be frozen;
- arithmetic/oracle reconciliation fails.

## Checkpoint acceptance

Checkpoint is optional and does not rewrite the baseline. It records:

- wave completed / assets migrated;
- actual costs to date;
- dual-run/decommission lag;
- approved vs received incentives to date;
- incidents/downtime to date;
- updated expected completion as a **new checkpoint estimate**, never as replacement of the original forecast;
- variance-to-date and evidence links.

## Outcome Verification acceptance

Required post-migration evidence:

- actual migration engineering/services/internal labour/transition costs;
- actual incentives received;
- post-migration normalized run cost;
- comparable pre/post observation windows;
- workload/demand normalization where material;
- actual duration/cutover/downtime;
- selected performance/SLO metrics where relevant;
- incident/reversal record;
- provenance/evidence strength per material field.

Required output:

`FROZEN FORECAST → ACTUAL → VARIANCE`

for at least:

- migration cost;
- duration;
- annual run cost;
- downtime;
- provider/partner incentive actually received.

If comparability is weak, the product reports weak comparability and must not call raw spend delta verified savings.

## Benchmark inclusion gate

A completed pilot can enter `VERIFIED_ONLY` benchmark cohorts only if:

- actual values exist for required benchmark fields;
- evidence strength meets the allowed threshold;
- evidence is sufficiently independent;
- pre/post comparability passes the cohort methodology;
- consent/data-use requirements are satisfied;
- no field is silently promoted from estimate/attestation to machine/document verified.

Otherwise the outcome remains useful at a lower evidence class but is excluded from verified-only aggregate claims.

## Founding-pilot customer deliverable

The human-readable report should be concise enough for an executive decision but traceable back to machine-readable evidence:

1. Executive verdict
2. Economics at a glance
3. Why this option won / why no switch was recommended
4. Incentive/subsidy disclosure
5. Key assumptions and UNKNOWNs
6. Evidence register
7. Forecast certificate
8. After migration: outcome/variance certificate
9. Methodology + hash/version appendix

## Success metrics for the Factory

For the first paid pilot, measure:

- paid amount;
- baseline human hours;
- evidence wait days;
- number of material UNKNOWNs at intake and resolution rate;
- number of manual evidence transformations;
- decision produced without product-truth exception: YES/NO;
- customer accepts forecast freeze: YES/NO;
- outcome-verification commitment obtained: YES/NO;
- any requested bespoke field/methodology change;
- willingness to pay for recurring benchmark/forecast-error intelligence after delivery: UNKNOWN until explicitly tested.

A free or synthetic run cannot satisfy the paid-pilot WTP gate.
