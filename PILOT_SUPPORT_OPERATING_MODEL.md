# ObraSignal — Assisted Pilot Support Operating Model

Status: `PREPARED / ASSISTED_PILOT / NOT_PRODUCTION_LAUNCH_AUTHORIZATION`

## Purpose

Give every controlled external pilot a coherent support route, severity model, escalation path, evidence standard, data-correction path, account/privacy path and billing-support path before the product is described as PILOT_READY.

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
Security exposure, tenant leak, destructive corruption, total outage of the pilot, critical false customer truth, unauthorized or cross-tenant account export, destructive deletion affecting the wrong tenant, or billing action that can create unauthorized financial impact.

Action: stop the affected unsafe path, preserve evidence, contain, repair/rollback safely, verify tenant/data boundaries, then resume only the affected capability when evidence supports it. P0 overrides ordinary development.

### P1
Core pilot workflow unavailable or materially incorrect for the customer, including inability to authenticate, complete password recovery, recover an expired authenticated session, reach relevant opportunity truth, persist a core action, access required account/privacy controls, or recover a required state.

### P2
Important defect with a safe workaround and no truth/security corruption.

### P3
Low-impact defect, cosmetic issue, or noncritical friction.

## Response workflow

`RECEIVE → ACKNOWLEDGE → CLASSIFY → REPRODUCE → CONTAIN IF NEEDED → DIAGNOSE → REPAIR/BYPASS → TEST → REGRESSION TEST → VERIFY CUSTOMER-RELEVANT STATE → COMMUNICATE → CLOSE`

A ticket is not closed merely because code changed. Closure requires evidence that the reported customer path is safe/correct or that a clearly communicated workaround resolves the pilot need.

## Security / tenant report path

Any report involving another company's data, guessed identifiers, copied links, authorization, stale sessions, exports, deletion state, notifications or background jobs is provisionally P0 until disproved. Do not ask a customer to continue exploring a suspected tenant leak to gather more evidence.

## Authentication / recovery path

For sign-in, password-recovery or expired-session reports:
1. record the exact journey stage and build SHA;
2. never ask for the customer's password, recovery token or raw access token;
3. distinguish identity-provider failure, redirect/return failure, local tenant-binding failure and protected-API authorization failure;
4. if a protected write returned 401, verify whether one session refresh was attempted and whether any duplicate mutation occurred before retrying manually;
5. confirm tenant-private local state is not hydrated under the wrong identity after sign-out/re-auth;
6. close only after the exact customer-relevant authentication path is verified or a safe workaround is explicitly communicated.

## Account export / deletion support

For account export or deletion requests:
- never request a customer to email exported private account JSON unless a minimal redacted excerpt is genuinely necessary for diagnosis;
- confirm the authenticated tenant identity before interpreting any export/deletion state;
- distinguish current canonical server-owned account data from shared public procurement data, identity-provider data, billing-provider source records and device-local private cache;
- destructive deletion must require the implemented explicit confirmation; support must not bypass it;
- `PENDING` means pending: product-private cleanup must not be represented as fully completed while external identity/session/device/billing revocation is unproved;
- `FAILED` or `UNKNOWN` must not be rewritten as success for convenience;
- any suspected cross-tenant export/deletion is P0 and the affected path must be contained immediately.

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
- account/privacy rights remain available independently of paid entitlement state;
- production billing activation remains an owner-controlled credential/action boundary.

## Operational review

For every active pilot, maintain a short daily operating view while the pilot is active:
- open P0/P1;
- new support issues;
- failed auth/recovery/API/jobs;
- account export/deletion requests in `PENDING`, `FAILED` or `UNKNOWN`;
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
- authentication/account/privacy failures have a safe diagnostic path;
- data correction has an owner workflow;
- billing questions have a safe route;
- known limitations are disclosed;
- no support promise exceeds the actual operating capacity.
