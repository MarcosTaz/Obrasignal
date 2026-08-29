# ObraSignal — Assisted Pilot Support Operating Model

Status: `PREPARED / ASSISTED_PILOT / NOT_PRODUCTION_LAUNCH_AUTHORIZATION`

## Purpose

Give every controlled external pilot a coherent support route, severity model, escalation path, evidence standard, data-correction path and billing-support path before the product is described as PILOT_READY.

## Customer support route

For an assisted pilot, the invitation/onboarding communication must identify one monitored ObraSignal mailbox as the support contact. Until a dedicated support address is activated and verified, use the existing ObraSignal operating mailbox already used for pilot outreach. Do not publish or promise a new address that has not been provisioned.

Every pilot welcome message must state:
- how to report a problem;
- what information is useful without exposing secrets or unrelated personal data;
- what constitutes an urgent issue;
- expected operating window for the assisted pilot;
- that security/data-isolation concerns should be marked urgent.

## Intake record

Each support issue must record:
- incident/support ID;
- reported_at;
- reporter/account;
- affected journey stage;
- short description;
- observed result;
- expected result;
- evidence/source links or screenshots where safely provided;
- severity;
- customer impact;
- tenant/security impact;
- workaround, if any;
- owner;
- status;
- root cause when known;
- corrective action;
- verification evidence;
- customer-visible resolution state.

Unknown fields remain `UNKNOWN`; do not invent root causes or resolution.

## Severity

### P0
Security exposure, tenant leak, destructive corruption, total outage of the pilot, critical false customer truth, or billing action that can create unauthorized financial impact.

Action: stop the affected unsafe path, preserve evidence, contain, repair/rollback safely, verify tenant/data boundaries, then resume only the affected capability when evidence supports it. P0 overrides ordinary development.

### P1
Core pilot workflow unavailable or materially incorrect for the customer, including inability to authenticate, reach relevant opportunity truth, persist a core action, or recover a required state.

### P2
Important defect with a safe workaround and no truth/security corruption.

### P3
Low-impact defect, cosmetic issue, or noncritical friction.

## Response workflow

`RECEIVE → ACKNOWLEDGE → CLASSIFY → REPRODUCE → CONTAIN IF NEEDED → DIAGNOSE → REPAIR/BYPASS → TEST → REGRESSION TEST → VERIFY CUSTOMER-RELEVANT STATE → COMMUNICATE → CLOSE`

A ticket is not closed merely because code changed. Closure requires evidence that the reported customer path is safe/correct or that a clearly communicated workaround resolves the pilot need.

## Security / tenant report path

Any report involving another company's data, guessed identifiers, copied links, authorization, stale sessions, exports, notifications or background jobs is provisionally P0 until disproved. Do not ask a customer to continue exploring a suspected tenant leak to gather more evidence.

## Data-correction workflow

When a customer disputes an opportunity, score, status or source field:
1. capture the exact source/external identifier and customer-visible state;
2. inspect provenance and authoritative source state;
3. distinguish source error, ingestion error, normalization error, relevance/profile issue and stale presentation;
4. correct only the appropriate owner layer;
5. preserve auditability;
6. verify no unrelated tenant/customer truth was changed;
7. tell the customer what changed and what remains uncertain.

Never rewrite source truth merely to satisfy a customer's preferred answer.

## Billing support

During controlled pilot/billing sandbox work:
- never request card numbers or payment credentials by email;
- distinguish provider state from local entitlement state;
- duplicate/out-of-order webhook evidence is retained;
- provider-unavailable conditions fail closed rather than fabricating paid entitlement;
- production billing activation remains an owner-controlled credential/action boundary.

## Operational review

For every active pilot, maintain a short daily operating view while the pilot is active:
- open P0/P1;
- new support issues;
- failed auth/API/jobs;
- stale-source warnings;
- notification failures;
- customer-blocking friction;
- first-value status;
- next customer follow-up.

This is an assisted-pilot procedure, not evidence that 24/7 support exists.

## Pilot support gate

A pilot may be considered support-capable only when:
- the customer has a verified contact route;
- intake and severity classification are operational;
- P0/P1 escalation is understood;
- data correction has an owner workflow;
- billing questions have a safe route;
- known limitations are disclosed;
- no support promise exceeds the actual operating capacity.
