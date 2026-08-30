# EU CLOUD SWITCHING / MIGRATION CAPITAL NETWORK — BATON

## Mission
Build a pilot-ready commercial product that answers whether an expensive infrastructure switching event should happen, what it will really cost, what migration capital is available, and whether promised economics materialized; then validate whether that product can acquire paid demand and compound into proprietary switching-outcome intelligence.

## Source truth
- Repository: `MarcosTaz/Obrasignal`
- Base branch: `factory/eu-cloud-switching-migration-capital`
- Base DRAFT PR: `#711`
- Current isolated T2 successor: `cloud-switching/t2-consent-trigger-dedup-20260829`
- Current DRAFT PR: `#802`
- Base HEAD used for successor: `60694599b42d705b22a5ceb4f51dda24b0636d42`.
- Base `Cloud Switching Quality` run #78 = SUCCESS on exact base HEAD.
- Successor exact-head CI must be checked after every mutation; never infer GREEN from the base.
- Global ObraSignal Quality includes unrelated repository/mobile checks and is not used to conceal or redefine this Factory's focused product truth.
- No automatic merge.

## Terminal scoreboard
- CURRENT_TERMINAL: **T1 — PILOT CAPABLE / T2 PREPARED NOT EXPOSED**
- NEXT_TERMINAL: **T2 — EXTERNAL WTP / FIRST-REVENUE SIGNAL**
- CURRENT_WEDGE: customer-paid independent VMware/infrastructure switching economic assurance with immutable `PROMISE → ACTUAL → VARIANCE`.
- CURRENT_BOTTLENECK: external willingness-to-pay remains unproven; public-trigger acquisition volume is alive but still not proven sufficient as a sole channel.

## T1 product truth
Implemented and focused-tested capabilities include:
- decision-ready infrastructure estate gate;
- duplicate/stale/UNKNOWN/missing-capacity/future-timestamp failures;
- baseline certainty KNOWN / ESTIMATED / ASSUMED / UNKNOWN;
- gross switching cost with transition categories: engineering, partner services, internal labour, training, parallel run, refactoring, contingency, data movement/egress, decommissioning, backup/DR, security and support transition;
- potential vs approved vs received incentives;
- subsidy separate from operating savings;
- economic vs customer-cash payback;
- over-subsidy cannot create negative payback duration;
- status-quo/renewal economics;
- provider-neutral alternatives with separate economic and customer-cash winners;
- immutable pre-migration forecast;
- retrospective rewrite protection;
- phased migrations, dual-run/decommission lag and renewal overlap;
- actual reconciliation and forecast-error fields;
- comparability gating;
- evidence-strength/independence gating for benchmark eligibility;
- case-level assisted-labour persistence and tenant isolation;
- synthetic positive/neutral/value-destroying companies;
- independent oracle;
- SWITCH / DO_NOT_SWITCH_NOW / RENEW_TEMPORARILY / NEEDS_MORE_EVIDENCE;
- tenant-isolated SQLite persistence, hashing, versioning, concurrency hardening and process-style restart;
- standalone pilot WSGI using canonical identity adapter.

## T2 acquisition research
- Earlier trigger universe: 30 researched records across PRE_DECISION / RENEWAL_OPEN / IN_PROGRESS / RECENT_DECISION / COMPLETED controls.
- Naive `VMware renewal = switching lead` assumption remains REJECTED.
- Strongest trigger sequence:
  `PRE-PROCUREMENT ESTIMATE / MARKET DIALOGUE → OR EQUIVALENT / REPLACEMENT / ALTERNATIVES → FORMAL TENDER → DECISION`.
- Trigger timing preserves publication→detection latency and deadline history.
- Public procurement channel remains `ALIVE_BUT_NOT_PROVEN_SUFFICIENT` as a sole acquisition channel.

### August 2026 public-source sample

`docs/cloud-switching/TRIGGER_VOLUME_SAMPLE_2026-08.md` now records a conservative additional snapshot:
- 13 distinct buyer decision events sampled;
- 5 clearly challengeable under text-only rules;
- 8 incumbent renewal/licensing/infrastructure events explicitly excluded from switching volume;
- no multiple notice/source revision is allowed to inflate the decision-event count.

This sample does **not** prove the working target of ~10 challengeable trigger-events/month. It does prove that naive keyword volume materially overstates acquisition capacity and that replacement/migration/`or equivalent`/market-dialogue language is the stronger public acquisition signal. Because this is not a near-exhaustive EU census, five is neither a monthly estimate nor an upper bound.

Scenario volume needed for five paid pilots/year remains hypothesis-only: ~16.7 triggers/month at 10% discovery×25% paid; ~9.3/month at 15%×30%; ~6.9/month at 20%×30%.

## Trigger de-duplication implementation
`cloud_switching.triggers.TriggerRecord` now separates a public notice/revision from the underlying organization+decision event.

`deduplicate_decision_events()`:
- counts one organization + one switching/renewal decision once;
- preserves notice/revision observations upstream;
- uses stable earliest publication/detection selection for commercial-volume counting;
- supports `count_challengeable_decision_events()` using only forecast-freeze-viable EARLY_DIALOGUE/ACTIONABLE observations.

This prevents multiple portals/revisions from becoming fabricated acquisition volume.

## Assisted-delivery economics
Working pricing hypotheses remain UNVALIDATED:
- Baseline Certification: EUR 1,500
- optional checkpoint: EUR 1,000
- Outcome Verification: EUR 3,500
- typical lifecycle: EUR 5,000–6,000

Assisted-hours model remains scenario-based until real work is measured:
- Baseline target: 10.5 h, planning range 8–14 h.
- Outcome target: 9.5 h, planning range 7–13 h.
- One-checkpoint lifecycle: 22 h.
- EUR 6k / 22 h = EUR 272.73 revenue per human hour before overhead.
- At EUR 100/h labour-equivalent, contribution scenario = EUR 3.8k / 63.3% before software/sales/admin.

Anti-consulting instrumentation persists labour categories including INTAKE, ESTATE, BILLING, STATUS_QUO, OPTIONS, MIGRATION_COST, INCENTIVE, FORECAST_FREEZE, COMPARABILITY, ACTUALS, PERFORMANCE, ORACLE_QA, REPORT and REWORK.

## Benchmark contribution / consent truth
Outcome verification and permission to contribute data are now separate product states.

`cloud_switching.contribution.OutcomeContributionConsent` distinguishes:
- `WITHHELD`;
- `INTERNAL_ANALYSIS_ONLY`;
- `DEIDENTIFIED_BENCHMARK`;
- aggregate publication as an additional separate permission.

A verified outcome is **not benchmark eligible** without explicit deidentified-benchmark consent. Withheld contribution cannot grant aggregate publication. Raw invoices/contracts/telemetry are never automatically benchmark-contributed.

Prior privacy design remains: no default peer cell <5 organizations; commercially sensitive metrics default to 10+ until re-identification risk is assessed; sparse/dominant cells are suppressed/merged.

## WTP evidence truth
`docs/cloud-switching/WTP_EVIDENCE_SCHEMA_V01.md` freezes the commercial ladder:

`NOT_EXPOSED → EXPOSED → REPLIED → PROBLEM_CONFIRMED → DATA_FEASIBLE → PRICE_PRESENTED → WTP_POSITIVE → PILOT_ACCEPTED → PAID`.

WTP requires explicit acceptance/counteroffer of a non-zero commercial basis. Delivery/open tracking, a meeting, “interesting”, free pilot acceptance or synthetic use do not prove WTP. PAID requires separate durable settlement evidence.

## Pilot acceptance contract
Founding pilot still requires identifiable decision boundary, decision-ready estate, status quo + credible change option, evidence-linked baseline, complete migration-cost categories or UNKNOWN, incentive lifecycle separation, frozen forecast, evidence permission, ability to reject/defer switch, post-migration actuals/comparability/provenance, and explicit benchmark-contribution consent if any benchmark inclusion is requested.

## Safety invariants
- Provider funding != our revenue.
- Provider incentive != savings.
- Executor/provider cannot self-grade as independent verifier.
- UNKNOWN cannot silently become zero or verified.
- Forecast cannot be rewritten after freeze.
- Different notice revisions/deadlines preserve lineage.
- Notice revisions/multiple portals cannot inflate one decision into multiple leads.
- Verified outcome != permission to contribute to benchmark.
- Public trigger evidence does not prove WTP.
- Synthetic/free usage does not prove WTP.

## DONE in current successor
1. Case-level labour persistence was already closed on the base branch.
2. Added explicit outcome-contribution/aggregate-publication consent states and tests.
3. Added organization+decision-event trigger de-duplication and tests.
4. Added fail-closed WTP evidence schema.
5. Added conservative August 2026 public trigger-volume sample without counting plain renewals as switching opportunities.

## ACTIVE
1. Continue toward a broader 60–90 day near-exhaustive EU public sample using the same decision-event de-duplication rule; current sample is not sufficient to prove ~10/month.
2. Build the first top-10 research-priority live prospect shortlist only from current/open decision events with evidence-backed challengeability and deadline/history.
3. Expand non-procurement trigger families only when the ultimate buyer is identifiable; anonymous job postings remain WEAK_SIGNAL/control data.
4. Refine labour/pricing only from measured or evidence-derived burden.

## NEXT
1. At authorized exposure, seek paid founding baseline first; do not count free use as WTP.
2. Measure actual publication→detection latency from a recurring collector rather than reconstructing it retrospectively.
3. After real WTP/outcomes, test recurring benchmark/forecast-error intelligence.
4. Only then re-run €1M/36-month and larger-scale control-point tests.

## WAIT
Genuine external dependencies:
- real customer estate/contract/billing/telemetry data;
- real migration quote/provider incentive approval;
- customer authorization;
- external outreach/send authorization and channel;
- contracts/payment;
- real external deployment/customer use.

Commercial proof remains **UNKNOWN**.

## RESUME_AT
Verify exact successor HEAD and focused Cloud Switching Quality. If GREEN, continue public trigger collection/shortlist research; if RED, repair immediately. Never reset into generic FinOps/cloud management and never inflate renewal notices into switching leads.
