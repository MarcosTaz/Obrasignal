# ObraSignal — Pilot Operations & Observability Runbook

Status: `RUNBOOK_READY / PRODUCTION_MONITORING_COVERAGE_NOT_FULLY_PROVED`

## Objective

Operate a controlled assisted pilot without treating unknown health as healthy. This runbook composes existing exact-build production smoke, auth health, source-health and latency signals into an operator procedure. It does not claim an external 24/7 monitoring service exists.

## Existing executable signals

### Exact deployed build / API health

The production smoke workflow checks that `/api/v1/health` returns:
- `ok=true`;
- service identity `obrasignal-api`;
- exact expected build SHA;
- provider auth mode configured;
- bounded provider-health state.

A deployment that responds but serves the wrong SHA is not considered healthy.

### Protected-route boundary

Production smoke verifies an unauthenticated `/api/v1/profile` request returns `401 authentication_required`.

### Browser-origin CORS boundary

Production smoke verifies the configured GitHub Pages origin receives the expected API preflight authorization headers.

### Deployed web shell

Production smoke verifies the public Pages shell responds and contains the ObraSignal marker. This is reachability/build evidence, not a human visual usability test.

### Source truth health

`source_health` tracks last attempt/success/failure, consecutive failures, last error, duration and successful observed counts. Failed fetch/ingestion must not be represented as a zero-opportunity market.

Derived states include freshness and health. Persistent failure plus stale/no successful observation can become `unavailable`; stale/failed observation can become `degraded`.

### Pipeline latency

`latency_health` compares recent stage latency with an older non-overlapping baseline. Current thresholds classify approximately:
- `<2×` historical average: healthy;
- `>=2×`: degraded;
- `>=4×`: critical.

This is a relative degradation signal, not an absolute customer-SLA promise.

### Authentication / account-state truth

The current client/API contract can distinguish ordinary authentication failure from one recoverable expired-session 401 on a protected request. A successful one-shot refresh is customer-journey recovery evidence; it is not permission to retry indefinitely or to assume a protected write succeeded when the final response is unknown.

Account deletion state is explicitly `NONE`, `PENDING`, `FAILED`, `UNKNOWN` or equivalent backend state. Product-private cleanup and external identity/session/device/billing revocation are separate boundaries. An operator must never infer `COMPLETED` from product-private cleanup alone.

## Assisted-pilot daily operating check

While a real pilot is active, inspect and record at least:

1. exact build expected vs served;
2. API health result;
3. auth provider state;
4. protected-route boundary smoke;
5. web-shell reachability;
6. source coverage status for sources used by that pilot;
7. source age / failure streaks;
8. failed ingestion/jobs visible in current source-health evidence;
9. unusual latency-health states where sufficient samples exist;
10. open P0/P1 support incidents;
11. failed sign-in/password-recovery/session-refresh reports affecting the pilot;
12. account export/deletion requests in `PENDING`, `FAILED` or `UNKNOWN`;
13. notification/provider failures affecting the pilot;
14. whether first/repeat-value work is blocked by technical health.

Record `UNKNOWN` for signals that are not available. Never convert “no alert received” into “healthy.” Never convert “no customer complaint” into proof that authentication, privacy or tenant boundaries are healthy.

## Incident triggers

Treat as at least P1, or P0 where truth/security is affected:

- served production build differs from intended build;
- auth boundary unexpectedly allows unauthenticated protected access;
- repeated authentication/recovery failure blocks the pilot's core journey;
- a protected write after session refresh produces possible duplicate or ambiguous mutation;
- suspected tenant leakage;
- account export contains another tenant's private state;
- destructive deletion targets the wrong tenant or bypasses explicit confirmation;
- deletion is communicated as complete while required external revocation is unproved;
- source represented as current when source health is unavailable/stale;
- destructive persistence corruption;
- current customer opportunity truth cannot be established safely;
- billing entitlement can be granted without provider authority;
- repeated failure blocks the pilot's core journey.

Suspected cross-tenant export/deletion or wrong-tenant destructive action is P0 until disproved.

## Source degradation policy

When a source is degraded/aging/stale/unavailable:
- preserve last known data with explicit freshness state where safe;
- do not claim zero results means zero market opportunities;
- do not silently upgrade stale observations to current;
- if currentness is required for a customer action, fail closed or require source confirmation;
- record customer impact if the source is material to an active pilot.

## Authentication / privacy degradation policy

When auth, recovery, export or deletion state cannot be proven:
- do not ask for passwords, recovery links/tokens, raw access tokens or provider secrets;
- do not manually repeat a protected write until duplicate-mutation risk is understood;
- verify the authenticated account/tenant through ordinary product identity rather than customer-supplied secrets;
- keep `FAILED` and `UNKNOWN` distinct from `PENDING` and from successful product-private cleanup;
- preserve account/privacy rights independently of paid entitlement state;
- contain the affected path immediately if another tenant may be implicated.

## Recovery verification

After an incident/fix:
- verify exact build SHA;
- rerun relevant boundary smoke;
- verify data/storage integrity where persistence was involved;
- verify source health has a new successful observation rather than merely clearing an error string;
- for auth/session incidents, verify the exact sign-in/recovery/refresh path and check that no duplicate protected mutation occurred;
- for export/deletion incidents, verify tenant scope, explicit confirmation and the exact final/pending boundary state;
- retest the affected customer journey;
- record remaining uncertainty.

## Current observability gap register

The following are not promoted to `PROVED` by this runbook alone:

- full client-side error aggregation in production;
- centralized server exception/error-rate alerting;
- externally verified uptime/SLO alerting;
- queue-depth/backlog alerts across every background process;
- exact-browser visual journey monitoring;
- customer funnel abandonment alerts;
- billing webhook operational alert routing;
- automated alerting for password-recovery/session-refresh failure rates;
- automated alerting for account export/deletion states stuck in `PENDING`/`FAILED`/`UNKNOWN`;
- 24/7 human on-call coverage.

For a small assisted pilot these can be partially covered by deliberate operator checks, but they remain material gaps before broad COMMERCIAL_READY/SCALE_READY claims.

Classification:

`G14_OBSERVABILITY / CORE_HEALTH_SIGNALS_PRESENT / PILOT_OPERATOR_RUNBOOK_READY / AUTH_PRIVACY_OPERATOR_CHECKS_ALIGNED / BROADER_ALERTING_GAPS_EXPLICIT / NOT_24X7 / NOT_SCALE_READY`
