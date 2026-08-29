# ObraSignal — Pilot Readiness Gate — 2026-08-29

Status: `NOT_YET_PILOT_READY / SAFE_PREPARATION_CONTINUES`

This gate deliberately separates technical proof, assisted operating readiness and real-customer evidence. It is not a release declaration.

## Gate 1 — Selected ICP/problem

**PARTIAL / NOT VALIDATED**

Current narrowed hypothesis: Portugal construction/electrical/AVAC contractors with demonstrated recurring public-procurement participation and a real internal opportunity-discovery/triage workflow.

Evidence:
- first broad cohort generated one negative reply showing sector fit alone does not prove portal-triage pain;
- second cohort is now qualified by procurement participation.

Missing:
- real confirmation from workflow-qualified prospects that discovery/triage is frequent and costly enough to matter.

## Gate 2 — Core product journey

**TECHNICALLY STRONG / EXACT LIVE PILOT JOURNEY NOT YET EXTERNALLY PROVED**

Candidate test stack covers signup/auth-related contracts, profile, radar/opportunity, watchlist/workflow, persistence, notification behavior, return mechanics and billing sandbox owners. Synthetic journeys are green on current integration heads.

Missing:
- one externally observed real customer completing the intended journey on a controlled deployable build;
- exact-browser visual/manual verification for the pilot build where current tooling has not supplied that evidence.

## Gate 3 — Customer truth/data

**TECHNICAL EVIDENCE STRONG**

Current stack includes canonical opportunity revision authority, stale-decision suppression, source-health/freshness semantics, historical schema truth preservation and failure atomicity.

Missing:
- real pilot observation that explanations/currentness are understandable and trusted by the target user.

## Gate 4 — Auth / tenant / security

**TECHNICAL TEST EVIDENCE STRONG / CONTINUOUS SECURITY REVIEW REMAINS**

Adversarial tenant tests, guessed-ID isolation, stale/missing provider auth fail-closed tests and protected route checks exist.

Gate remains blocked by any future discovered P0; there is no assertion that all possible security failure modes are exhausted.

## Gate 5 — Persistence / recovery / reliability

**TECHNICAL EVIDENCE STRONG**

Proved in candidate stack:
- persistence contract;
- backup/verified restore;
- concurrent first-start serialization;
- historical partial-schema migration;
- duplicate/retry idempotency;
- transaction rollback and ambiguous external-side-effect fail-closed behavior.

No automatic production cutover is authorized by backup tests.

## Gate 6 — Support

**PROCESS READY FOR ASSISTED PILOT / ACTIVATION PENDING**

Support operating model, severity, incident template, data-correction path and daily pilot operating review are prepared.

Missing:
- support route explicitly communicated to an accepted real pilot;
- real support load evidence.

## Gate 7 — Observability

**BOUNDED PILOT RUNBOOK READY / BROADER PRODUCTION COVERAGE INCOMPLETE**

Existing exact-build smoke, auth health, source-health and latency signals can support deliberate assisted-pilot checks.

Missing before broad commercial scale:
- full client/server error aggregation and alerting;
- external uptime/SLO monitoring;
- broader backlog/webhook alert routing;
- 24/7 human coverage if ever promised.

## Gate 8 — First value

**DEFINED / NOT OBSERVED**

Candidate FVE: a real customer judges a current, traceable, previously untriaged opportunity useful enough to investigate, save or assign.

No synthetic event can satisfy this gate.

## Gate 9 — Repeat value

**DEFINED / NOT OBSERVED**

Requires a separate later work cycle in which the customer returns and receives useful triage/opportunity value again.

D1/D7/D30 remain unobservable until real time windows elapse.

## Gate 10 — Billing / willingness to pay

**TECHNICAL BILLING EVIDENCE EXISTS / COMMERCIAL EVIDENCE ABSENT**

Billing lifecycle tests are not payment evidence. Current observed paid customers and revenue in the tracked GTM cohort are zero.

Missing:
- concrete paid continuation offer to a value-receiving real pilot;
- payment behavior;
- production billing owner credentials/activation where required.

## Gate 11 — Unit economics

**NOT ESTABLISHED**

Measurement structure exists. Revenue/customer, CAC, LTV, retention, support cost/customer and contribution margin are not yet validated.

## Gate 12 — No unresolved P0

**NO CURRENT P0 IDENTIFIED IN THE CONTROLLED CANDIDATE EVIDENCE / NOT A PERMANENT GUARANTEE**

Any discovered tenant leak, destructive corruption, critical false customer truth or unsafe billing behavior immediately blocks pilot exposure until contained and verified.

## Current decision

ObraSignal is **not yet legitimately `PILOT_READY`** because the selected problem has not been confirmed by workflow-qualified external prospects and the intended real-customer first-value path has not yet been observed. This is a commercial-evidence gap, not a reason to build arbitrary new features.

## Highest-value next transition

`WORKFLOW-QUALIFIED PROSPECT → PROBLEM CONFIRMATION → CONTROLLED ASSISTED PILOT → FIRST VALUE → REPEAT VALUE → PAID CONTINUATION TEST`

All preparation around this transition can continue autonomously. The outbound real-customer communication itself remains an explicit external action boundary.
