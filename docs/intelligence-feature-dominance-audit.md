# Feature dominance / counterfactual audit

Status: repository-safe synthetic measurement candidate. No merge/deploy/live weights/live thresholds/ranking rollout.

Base lineage: #484 exact-head `e65bb14d4b90524de40d45bf023ff036915cb9c7`, which already includes #477 matching normalization and PT corpus v2.

## Measurement contract

For controlled feature changes the audit records base score, new score, delta, controlled rank delta, reason delta, threshold crossings and actionability impact when applicable.

Surfaces are separated:
- commercial_score_v2: CPV, text, deadline, value, procedure;
- personalized_score: text/profile keyword, country, CPV, value;
- opportunity_match_pipeline: effective personalized score, lot score, blockers and decision.

One changed semantic input may legitimately feed more than one downstream rule. The audit does not call that pure unless the measured layer proves only one component changed. Deadline/value counterfactuals that trigger a hard blocker are recorded as actionability effects rather than being misrepresented as ordinary score influence.

## Current threshold registry under measurement

- commercial labels: 50 / 65 / 80
- personalized labels: 60 / 75 / 90
- lot labels: 50 / 65 / 80
- decision path: 60 / 65 / 75
- no-positive-evidence effective cap: 59
- hard-blocker effective cap: 35

These numbers are observed implementation thresholds, not business truth, probability cutoffs or calibrated relevance boundaries. #478 remains the semantic-authority WAIT item.

## Safety boundaries

- SCORE != CONFIDENCE.
- WEIGHT != EMPIRICAL IMPORTANCE.
- THRESHOLD != BUSINESS TRUTH.
- Synthetic rank deltas use a controlled candidate set and do not prove market ranking quality.
- No production/customer data.
- No autonomous weight/threshold change.
