# Founder Control Center

Private, fail-closed control plane for the founder portfolio.

## Invariants

- `UNKNOWN != GREEN`
- stale, future-dated or sourceless operational evidence cannot remain trusted current truth
- delayed feed evidence cannot overwrite newer canonical evidence
- dashboard state never replaces source-of-truth systems
- every material operational status carries source/freshness metadata
- concurrent source feeds must not silently overwrite one another
- source connectivity does not imply freshness or correctness
- custom KPIs cannot shadow canonical revenue, pipeline or customer truth
- RED actions never execute autonomously
- YELLOW controls are approval gates only; they do not execute an external action or claim a preparation artifact exists
- GREEN actions are read-only or internal/non-destructive
- no credentials are exposed to the browser

## Current MVP

- private founder authentication with stable server-side session secret
- CSRF protection for founder mutations and hardened response headers
- normalized Company Manifest model for current and future companies
- all known portfolio items visible from first boot
- ACTIVE / NEXT / WAIT per company and authenticated source-aware Factory feeds
- CEO attention ranking with explicit uncertainty and escalation for degraded/stale evidence
- central highest-value Action Center
- GREEN / YELLOW / RED authority enforcement
- persistent SQLite registry, audit log and company state snapshots
- atomic per-company read/modify/write for concurrent Factory, metric and founder-control updates
- production snapshot retention capped at the newest 2,000 state snapshots per company
- read-only GitHub repository, CI and deployment adapters
- strict GitHub owner/repository boundary before authenticated API calls
- unusable GitHub credential values are treated as not configured and are not sent to GitHub
- strict CI truth: only explicitly successful completed checks prove GREEN; neutral/skipped/pending remain UNKNOWN
- application health adapter with public-network and same-host redirect constraints
- canonical server-to-server business metric feed for revenue, pipeline and customers
- canonical source-owned numeric KPI feed for additional operational metrics
- out-of-order and materially future-dated Factory/metric evidence rejected
- provenance inventory separates unique connected source labels from connected evidence-boundary counts and independently evaluates freshness
- readiness diagnostics that reveal configuration state without returning secret material
- normalized per-company APIs for metrics, Factory state, risks, revenue, history, provenance and actions
- responsive desktop/mobile UI including source-owned KPI values and evidence
- Gunicorn WSGI entrypoint and container definition for a private deployment; deployment itself is not automatic

## Run locally

```bash
export FCC_ADMIN_TOKEN='use-a-long-random-secret'
export FCC_SESSION_SECRET='use-another-long-random-secret'
export FCC_SECURE_COOKIE=0
python -m founder_control_center.app
```

Open `http://127.0.0.1:8088`.

Keep `FCC_SECURE_COOKIE=1` behind HTTPS.

## Container build

```bash
docker build -f founder_control_center/Dockerfile -t founder-control-center .
```

The container defaults to a single Gunicorn worker and `FCC_DB=/data/founder_control_center.db`. Mount `/data` on persistent storage for durable registry, audit and history state. The production WSGI entrypoint installs a SQLite trigger that retains only the newest 2,000 snapshots per company and prunes older excess. This SQLite topology is intentionally single-instance; horizontal scaling requires a canonical shared database before replicas can be trusted.

## Tests

```bash
python -m unittest discover -s founder_control_center/tests -v
```

The dedicated pull-request workflow checks out the exact PR head, verifies the revision, compiles the package, runs the unit/integration suite, builds the private image, then starts that image with CI-only credentials. It proves liveness, performs a real founder login, reads the authenticated readiness endpoint and company registry, and verifies required seed companies. It does not merge or deploy.

## Live integrations

Public GitHub repositories can be refreshed read-only without credentials. Set `FCC_GITHUB_TOKEN` to enable private-repository truth and improve API allowance. Repository identifiers are constrained to an `owner/name` boundary before the server token can be used. GitHub tokens that fail the same minimal usability floor reported by readiness are treated as absent and are not sent. An invalid or inaccessible repository remains `UNKNOWN`.

GitHub deployment status is a separate evidence channel from repository CI. Application transport health is separate again: HTTP/process health does not prove business correctness.

Factories can push only their own `ACTIVE / NEXT / WAIT` state through `/api/ingest/factory-state` using the separate `FCC_FACTORY_INGEST_TOKEN`. A Factory feed cannot overwrite global company truth. Old evidence becomes `STALE`; delayed evidence is rejected if newer evidence for that Factory is already stored. Conflicting payloads at an identical observation time are rejected rather than silently choosing one truth.

Canonical billing/CRM adapters can push only `revenue`, `pipeline` or `customers` through `/api/ingest/business-metric` using `FCC_METRIC_INGEST_TOKEN`. Every value requires explicit source, observation time and freshness. A null value is forced to `UNKNOWN`; the endpoint does not infer revenue or customers from product activity. Canonical business units cannot be relabelled without an upstream conversion.

Other canonical operational sources can publish numeric KPIs through `/api/ingest/metric` with the same dedicated metric-feed token. Each KPI requires a non-reserved slug key, bounded label and source. These values live in `company.metrics`; they cannot overwrite `revenue`, `pipeline` or `customers`. Null values become `UNKNOWN`, and delayed/future or same-time contradictory evidence is rejected. Bounded metadata is rejected rather than silently truncated.

Founder-authenticated diagnostics include:

- `/api/readiness` — configuration readiness only, never credential values;
- `/api/companies/<company_id>/sources` — provenance/freshness inventory with source-label and evidence-boundary counts kept separate;
- `/api/companies/<company_id>/history` — bounded read window over retained state snapshots;
- `/api/audit` — recent action/evidence-ingestion audit events.

## Security and authority status

`FCC_ADMIN_TOKEN`, `FCC_SESSION_SECRET`, Factory/metric ingest tokens and optional GitHub credentials remain server-side. Founder session mutations require CSRF validation. Missing or materially weak required private-session configuration fails closed.

Health checks reject localhost/private/non-global destinations and do not automatically follow arbitrary redirects. Deployment metadata cannot silently grant health-check authority to an unsafe environment URL. Repository identifiers cannot inject extra GitHub API path/query authority.

The current health adapter validates DNS answers before a request, but the HTTP client subsequently resolves the hostname again. Therefore DNS rebinding between validation and connection remains a residual SSRF/TOCTOU risk. Do not treat the current health network policy as complete SSRF isolation until connection-time address pinning (with correct TLS/SNI handling) is implemented and tested.

2FA/IdP integration remains `UNKNOWN / NOT CONNECTED`. Production deployment, merge, billing changes, external communications, destructive data operations and irreversible commitments remain owner-controlled and are not executed by this MVP.
