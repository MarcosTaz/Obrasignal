# ObraSignal — Pilot Readiness Gate — 2026-08-30

Status: `NOT_YET_PILOT_READY / SAFE_PREPARATION_CONTINUES`

This gate separates technical proof, assisted operating readiness and real-customer evidence. It is not a release declaration and does not authorize external exposure.

## Gate 1 — Selected ICP/problem

**PARTIAL / NOT VALIDATED**

Current narrowed hypothesis: Portugal construction/electrical/AVAC contractors with demonstrated recurring public-procurement participation and a real internal opportunity-discovery/triage workflow.

Evidence:
- first broad cohort generated one negative reply showing sector fit alone does not prove portal-triage pain;
- second cohort is more tightly qualified by procurement participation and verified public contact paths where evidence exists.

Missing:
- real confirmation from workflow-qualified prospects that discovery/triage is frequent and costly enough to matter.

## Gate 2 — Core product journey

**TECHNICALLY STRONG / EXACT REAL PILOT JOURNEY NOT YET EXTERNALLY PROVED**

Current candidate lineage covers authentication, email-confirmation handling where required, password recovery, one-shot expired-session recovery for authenticated writes, tenant-private local-state binding, profile, radar/opportunity, save/watchlist, workflow, persistence, notifications, billing gates and authenticated account/privacy controls.

Latest exact-green engineering parent entering this company composition: `de581341b0b6bbd309012cceff218d755aa62b88`, Quality #4258, **1030 passed / 2 skipped**, Mobile GREEN.

Missing:
- one externally observed real customer completing the intended journey on a controlled exact build;
- real-device/browser validation for the exact pilot build where repository CI cannot supply that evidence.

## Gate 3 — Customer truth/data

**TECHNICAL EVIDENCE STRONG**

Current stack includes canonical opportunity revision authority, stale-decision suppression, source-health/freshness semantics, historical schema truth preservation, malformed-input handling, deterministic pagination and failure atomicity.

Missing:
- real pilot observation that explanations/currentness are understandable and trusted by the target user.

## Gate 4 — Auth / tenant / security

**TECHNICAL TEST EVIDENCE STRONG / CONTINUOUS SECURITY REVIEW REMAINS**

Adversarial tenant tests, guessed-ID isolation, stale/missing provider-auth fail-closed tests, tenant-private local-storage binding and protected-route checks exist. Password-recovery and expired-token protected-write recovery are now part of the customer journey evidence.

Account export is tenant-scoped. Destructive account deletion requires exact explicit confirmation. Product-private cleanup is not represented as fully completed while external identity/session/device/billing revocation is unproved.

Gate remains blocked by any future discovered P0; no assertion is made that all possible security failure modes are exhausted.

## Gate 5 — Persistence / recovery / reliability

**TECHNICAL EVIDENCE STRONG**

Proved in candidate stack:
- persistence contract;
- backup/verified restore;
- concurrent first-start serialization;
- historical partial-schema migration;
- duplicate/retry idempotency;
- transaction rollback and ambiguous external-side-effect fail-closed behavior;
- one-shot authenticated session refresh for a protected 401 without widening unauthenticated requests.

No automatic production cutover is authorized by these tests.

## Gate 6 — Support

**PROCESS READY FOR ASSISTED PILOT / ACTIVATION PENDING**

Current composition contains:
- support operating model and P0–P3 severity;
- incident/support record template;
- authentication/recovery diagnostic path;
- account export/deletion support path;
- data-correction path;
- safe billing support rules;
- daily assisted-pilot operating review.

Missing:
- support route explicitly communicated to an accepted real pilot;
- real support-load evidence.

## Gate 7 — Observability

**BOUNDED PILOT RUNBOOK READY / BROADER PRODUCTION COVERAGE INCOMPLETE**

Existing exact-build smoke, auth health, source-health and latency signals can support deliberate assisted-pilot checks.

Missing before broad commercial scale:
- full client/server error aggregation and centralized alerting;
- external uptime/SLO monitoring;
- broader backlog/webhook alert routing;
- 24/7 human coverage if ever promised.

These scale gaps do not justify fabricating a `PILOT_READY` label, and they do not require arbitrary feature expansion before a controlled assisted pilot if the exact activation checklist is otherwise satisfied.

## Gate 8 — First value

**DEFINED / NOT OBSERVED**

Candidate FVE: a real customer judges a current, traceable, previously untriaged opportunity useful enough to investigate, save, assign or otherwise act on.

If the opportunity was already known to the customer, record explanation/triage value separately; do not claim discovery. No synthetic event can satisfy this gate.

## Gate 9 — Repeat value

**DEFINED / NOT OBSERVED**

Requires a separate later work cycle in which the customer returns and receives useful triage/opportunity value again. Repeated clicks or saves in one session do not establish repeat value.

D1/D7/D30 remain unobservable until real time windows elapse.

## Gate 10 — Billing / willingness to pay

**TECHNICAL BILLING EVIDENCE EXISTS / COMMERCIAL EVIDENCE ABSENT**

Billing lifecycle tests are not payment evidence. Account/privacy rights remain independent of paid entitlement. Current observed paid customers and revenue are zero.

Missing:
- concrete paid continuation offer to a value-receiving real pilot;
- observed willingness-to-pay/payment behavior;
- production billing owner credentials/activation where required.

## Gate 11 — Unit economics

**NOT ESTABLISHED**

Measurement structure exists. Revenue/customer, CAC, LTV, retention, support cost/customer, gross/contribution margin and payback are not yet validated.

## Gate 12 — No unresolved P0

**NO CURRENT P0 IDENTIFIED IN THE CONTROLLED CANDIDATE EVIDENCE / NOT A PERMANENT GUARANTEE**

Any discovered tenant leak, wrong-tenant export/deletion, destructive corruption, critical false customer truth or unsafe billing behavior immediately blocks pilot exposure until contained and verified.

## Current decision

ObraSignal is **not yet legitimately `PILOT_READY`** because the selected problem has not been confirmed by workflow-qualified external prospects and the intended real-customer first-value path has not been observed. The current decisive gap is real-world evidence, not missing arbitrary product breadth.

## Highest-value next transition

`WORKFLOW-QUALIFIED PROSPECT → PROBLEM CONFIRMATION → CONTROLLED ASSISTED PILOT → FIRST VALUE → REPEAT VALUE → PAID CONTINUATION TEST`

All reversible preparation around this transition may continue. Sending real prospect/customer communications, activating production billing, legal/public-position approval, protected merge/deploy and real-pilot activation remain explicit owner-controlled boundaries.
