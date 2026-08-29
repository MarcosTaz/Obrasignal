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
11. notification/provider failures affecting the pilot;
12. whether first/repeat-value work is blocked by technical health.

Record `UNKNOWN` for signals that are not available. Never convert “no alert received” into “healthy.”

## Incident triggers

Treat as at least P1, or P0 where truth/security is affected:

- served production build differs from intended build;
- auth boundary unexpectedly allows unauthenticated protected access;
- suspected tenant leakage;
- source represented as current when source health is unavailable/stale;
- destructive persistence corruption;
- current customer opportunity truth cannot be established safely;
- billing entitlement can be granted without provider authority;
- repeated failure blocks the pilot's core journey.

## Source degradation policy

When a source is degraded/aging/stale/unavailable:
- preserve last known data with explicit freshness state where safe;
- do not claim zero results means zero market opportunities;
- do not silently upgrade stale observations to current;
- if currentness is required for a customer action, fail closed or require source confirmation;
- record customer impact if the source is material to an active pilot.

## Recovery verification

After an incident/fix:
- verify exact build SHA;
- rerun relevant boundary smoke;
- verify data/storage integrity where persistence was involved;
- verify source health has a new successful observation rather than merely clearing an error string;
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
- 24/7 human on-call coverage.

For a small assisted pilot these can be partially covered by deliberate operator checks, but they remain material gaps before broad COMMERCIAL_READY/SCALE_READY claims.

Classification:

`G14_OBSERVABILITY / CORE_HEALTH_SIGNALS_PRESENT / PILOT_OPERATOR_RUNBOOK_READY / BROADER_ALERTING_GAPS_EXPLICIT / NOT_24X7 / NOT_SCALE_READY`
