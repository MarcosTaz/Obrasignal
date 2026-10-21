# Cloud Switching — Benchmark Data Contribution v0.1

Status: product/governance design only. Not legal advice and not a customer agreement.

## Purpose

Allow a verified migration outcome to improve cross-provider benchmark intelligence without turning raw customer evidence into a resale dataset or allowing providers/executors to grade themselves.

## Contribution principle

`verified customer outcome → explicit contribution choice → de-identification/minimum-cohort gate → benchmark aggregate`

Raw billing exports, contracts, invoices, telemetry and architecture artefacts remain evidence for the customer's own verification package. They are not automatically benchmark-contributed merely because they were uploaded for analysis.

## Separate permissions

A real customer workflow should distinguish at least:

1. `PROCESS_FOR_CUSTOMER_REVIEW` — necessary to deliver the contracted review.
2. `RETAIN_VERIFICATION_RECORD` — retain the normalized outcome/evidence lineage for the agreed retention period.
3. `CONTRIBUTE_DEIDENTIFIED_BENCHMARK_FIELDS` — optional benchmark contribution.
4. `ALLOW_AGGREGATE_PUBLICATION` — optional use in aggregated statistics meeting cohort/privacy rules.

No checkbox/consent state should be silently inferred from another.

## Candidate benchmark-contributed fields

Prefer normalized/minimized fields rather than raw documents:

- source platform/provider class;
- destination platform/provider class;
- workload class;
- architecture pattern;
- migration strategy;
- geography band where cohort-safe;
- scale band rather than exact identifiers where appropriate;
- normalized pre-run cost;
- normalized post-run cost;
- gross migration investment;
- customer cash investment;
- received incentive amount or incentive ratio;
- duration/cutover/downtime bands or normalized values;
- forecast error for cost/duration/run-cost/incentive/payback;
- evidence grade;
- comparability grade;
- methodology version;
- observation window metadata.

Do not contribute customer names, contract IDs, invoice numbers, account IDs, raw resource IDs or free-text evidence by default.

## Cohort disclosure gate

Initial conservative product rule:

- no peer benchmark cell with fewer than 5 independent organizations;
- for commercially sensitive economic metrics, default to 10+ organizations until re-identification risk is separately assessed;
- do not publish a cell where one organization dominates the cohort economically or where route/geography/scale combination makes members obvious;
- merge/suppress sparse dimensions instead of fabricating precision.

These thresholds are product safeguards, not claims of statutory anonymity.

## Independence rules

- migration executor/provider may supply evidence but may not unilaterally mark its outcome `INDEPENDENT_VERIFIED`;
- customer attestation alone remains distinguishable from document/machine verification;
- provider-funded cases remain eligible only if subsidy is disclosed separately and verification remains independent;
- benchmark access/ranking must not be secretly influenced by provider compensation.

## Contribution incentive hypothesis

Do not pay for favourable outcomes.

Candidate mechanism:

`contribute verified/deidentified outcome → receive deeper cohort benchmark access or discounted recurring intelligence`

Reward evidence quality/completeness, never whether migration succeeded or whether a provider looks good.

## Withdrawal / retention concept

A future customer agreement needs explicit treatment of:

- source evidence retention/deletion;
- normalized individual record retention;
- future benchmark use after withdrawal;
- whether already-computed aggregates can remain where lawful/agreed and no longer identify the contributor;
- backup deletion timelines.

The product must not promise legal deletion semantics before storage/backups can actually enforce them.

## Data-quality gate before benchmark inclusion

Each outcome must retain:

- evidence record references;
- evidence-strength class;
- comparability result;
- methodology version;
- normalization-engine version;
- observation window;
- independent-verification status;
- contribution/consent state.

A field that is UNKNOWN or estimated must never be silently promoted to verified because it appears in a completed customer report.

## Anti-moat-theatre rule

Do not call the benchmark a defensible dataset merely because rows exist.

The moat hypothesis strengthens only when:

1. independent verified outcomes accumulate;
2. comparable cohorts become non-sparse;
3. customers repeatedly use benchmark/forecast-error intelligence;
4. contributors have a reason to keep adding outcomes;
5. prediction/decision quality demonstrably improves with proprietary outcome history.
