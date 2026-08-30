# ObraSignal — Project Completion Gate Status — 2026-08-30

Status: `PROJECT_NOT_COMPLETE / INTEGRATED_CANDIDATE / NOT_PRODUCTION_AUTHORIZATION`

This document reconciles the strongest currently composed engineering evidence with the real company/commercial evidence. Synthetic, CI, manual, or repository evidence is never promoted into real customer validation.

## Gate A — Thesis / real problem

**Status: PARTIAL / NOT VALIDATED**

Observed real outreach remains: 10 initial messages, 9 follow-ups, one inbound reply, zero positive replies, zero qualified conversations, zero meetings, zero pilots, zero payments. The one observed reply was negative and materially narrowed the ICP: sector fit alone does not establish a recurring public-procurement discovery/triage problem.

Required to advance: workflow-qualified prospects must confirm the problem from their actual process.

## Gate B — Product

**Status: STRONG INTEGRATED CANDIDATE / NOT CANONICAL RELEASE**

The current integration lineage covers authentication, password recovery, expired-token write recovery, tenant-private state, billing gates, authenticated account export/deletion controls, deletion-lifecycle preflight and device-private purge/session locking, opportunity discovery and explanations, workflow, saving/watchlist access, notifications, persistence/recovery, deterministic pagination, large-organization saved/workflow scale, and decision-history lookup performance.

Latest exact-green engineering head in this composition lineage: `2aec3b9cb03beef9cf7f7f446de30b108f9e9383`, Quality #4279, **1036 passed / 2 skipped**, Mobile GREEN.

No merge to main or production deployment is authorized by this status.

## Gate C — Customer journey

**Status: SYNTHETICALLY STRONG / REAL JOURNEY OPEN**

Synthetic account/profile → opportunity → explanation → workflow/save → watchlist → persistence paths are covered. Password recovery is covered. Account export and deletion-status/request controls are exposed to authenticated customers outside the billing entitlement gate. Expired-token protected writes attempt one authenticated session refresh before failing. Before an authenticated private shell is exposed, deletion lifecycle state is checked; non-`NONE` deletion states lock the private shell. After product-private server deletion is accepted, hydrated private UI is hidden, tenant-private device cache purge is attempted and the authenticated session is ended or remains visibly locked if session termination cannot be confirmed. Real first value by a workflow-qualified customer has not been observed.

## Gate D — Data / truth

**Status: STRONG CANDIDATE**

Source provenance, lifecycle/currentness, stale-decision suppression, source-health truth, malformed-input handling and bounded pagination are protected by the existing suite. A zero result is not represented as proof of zero market when coverage is uncertain.

## Gate E — Tenant / security

**Status: STRONG CANDIDATE / CONTINUOUS GATE**

Cross-tenant guessed-ID and hostile-tenant paths are covered by adversarial synthetic tests; tenant-private workflow, watchlist, notification and account/privacy paths remain fail-closed. Account export is tenant-scoped. Destructive account deletion requires explicit exact confirmation and does not overclaim completion while external revocation remains unproved. Stale local private data is not deliberately exposed while deletion lifecycle authority is unknown or non-active; accepted product deletion locks the hydrated shell before asynchronous local cleanup. Any real tenant/security report is provisionally P0 until disproved.

## Gate F — Billing

**Status: TECHNICALLY TESTED / PRODUCTION + COMMERCIAL OPEN**

Trial/unpaid/active/cancelled, stale/duplicate provider state and provider-unavailable paths are sandbox-tested. Account/privacy rights are not hidden behind billing entitlement state. Real payment instruments are not used. Production billing credentials/activation remain owner-controlled. Willingness-to-pay is unproved.

## Gate G — Support

**Status: ASSISTED-PILOT PROCESS PREPARED**

The support operating model defines P0–P3, intake, containment, repair, verification, customer communication, auth/recovery, account/privacy, data-correction and safe billing support. This does not claim 24/7 support.

## Gate H — Operations / observability

**Status: PARTIAL**

Source-health, latency-health and exact-build smoke owners exist, plus an assisted-pilot operations runbook aligned with auth/privacy lifecycle states. Broader centralized alerting, external uptime/SLO monitoring, complete client error aggregation, automated recovery/deletion-state alerting and 24/7 human on-call are not claimed.

## Gate I — Market exposure

**Status: NEGATIVE / PRELIMINARY**

Cohort 1 produced no positive evidence. Cohort 2 is more tightly qualified by demonstrated public-procurement participation, with verified contact paths where evidence exists. Prepared outreach remains NOT SENT unless explicitly owner-authorized.

## Gate J — First value

**Status: DEFINED / NOT REAL**

Candidate first-value event: a current, previously untriaged opportunity is surfaced with traceable source evidence and the real customer judges it useful enough to investigate, save, assign, or otherwise act on. If already known, record triage/explanation value separately; do not claim discovery.

## Gate K — Repeat value

**Status: NOT OBSERVED**

Requires a separate later work cycle with a real customer. Repeated actions in one synthetic or customer session do not establish repeat value.

## Gate L — Commercial

**Status: NOT PROVED**

Observed revenue: €0. Paying customers: 0. Active real pilots: 0. Validated price: UNKNOWN. No pricing hypothesis is treated as validated.

## Gate M — Unit economics

**Status: NOT ESTABLISHED**

CAC, LTV, gross margin, retention and payback remain unknown/not measurable from current real evidence. The unit-economics template is prepared to record future observed values without fabrication.

## Gate N — Quality / release engineering

**Status: STRONG INTEGRATED CANDIDATE / NOT FINAL RELEASE**

Release-gate evidence includes exact-head CI, composition, E2E fixtures, tenant/auth, password recovery, expired-session protected-write recovery, persistence, backup/restore, concurrent first start, historical/partial schema, idempotency, failure handling, account/privacy customer controls, deletion lifecycle preflight/local privacy locking and purge, mobile/web build smoke, synthetic business cases, adversarial tests, and no known regression on the latest exact-green engineering parent.

Remaining release truth includes exact-head validation of any later composition, final controlled release review, and any real-browser/production verification explicitly required before activation. A draft integration stack is not canonical merely because CI is green.

## Gate O — Owner-only boundaries

**Status: ISOLATED / NOT RESOLVED**

Owner-controlled or irreversible actions remain:
- send real prospect/customer communications;
- approve legal/privacy positions and public notices/terms;
- activate production billing credentials/payment behavior;
- merge protected release branches;
- deploy/promote production;
- authorize a real controlled pilot after the activation checklist is satisfied.

External account-deletion completion remains unproved until identity/session/device/billing-provider revocation boundaries have executable owner evidence; local product/device protections do not convert that external pending state into completion.

## Completion decision

`PROJECT_COMPLETE = FALSE`

The decisive open sequence is:

`WORKFLOW-QUALIFIED PROBLEM CONFIRMATION → CONTROLLED REAL PILOT → FIRST VALUE → REPEAT VALUE → WILLINGNESS TO PAY / PAYMENT → RETENTION + UNIT ECONOMICS → FINAL RELEASE/OWNER GATES`

Engineering green lowers pilot risk. It does not substitute for any item in that real-world sequence.
