# Founder Control Center

Private, fail-closed control plane for the founder portfolio.

## Invariants

- `UNKNOWN != GREEN`
- stale, future-dated or sourceless operational evidence cannot remain trusted current truth
- delayed feed evidence cannot overwrite newer canonical evidence
- dashboard state never replaces source-of-truth systems
- every material operational status carries source/freshness metadata
- concurrent source feeds must not silently overwrite one another
- RED actions never execute autonomously
- YELLOW actions prepare only and require founder approval
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
- read-only GitHub repository, CI and deployment adapters
- strict CI truth: only explicitly successful completed checks prove GREEN; neutral/skipped/pending remain UNKNOWN
- application health adapter with public-network and same-host redirect constraints
- canonical server-to-server business metric feed for revenue, pipeline and customers
- out-of-order and materially future-dated Factory/business evidence rejected
- provenance inventory per company with source, kind, observation time and independent freshness
- readiness diagnostics that reveal configuration state without returning secret material
- normalized per-company APIs for metrics, Factory state, risks, revenue, history, provenance and actions
- responsive desktop/mobile UI
- container definition for a private deployment; deployment itself is not automatic

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

The container defaults to a single Gunicorn worker and `FCC_DB=/data/founder_control_center.db`. Mount `/data` on persistent storage for durable registry, audit and history state. This SQLite topology is intentionally single-instance; horizontal scaling requires a canonical shared database before replicas can be trusted.

## Tests

```bash
python -m unittest discover -s founder_control_center/tests -v
```

The dedicated pull-request workflow also compiles the package and builds the private deployment image without deploying it.

## Live integrations

Public GitHub repositories can be refreshed read-only without credentials. Set `FCC_GITHUB_TOKEN` to enable private-repository truth and improve API allowance. An inaccessible repository remains `UNKNOWN`.

GitHub deployment status is a separate evidence channel from repository CI. Application transport health is separate again: HTTP/process health does not prove business correctness.

Factories can push only their own `ACTIVE / NEXT / WAIT` state through `/api/ingest/factory-state` using the separate `FCC_FACTORY_INGEST_TOKEN`. A Factory feed cannot overwrite global company truth. Old evidence becomes `STALE`; delayed evidence is rejected if newer evidence for that Factory is already stored.

Canonical billing/CRM adapters can push only `revenue`, `pipeline` or `customers` through `/api/ingest/business-metric` using `FCC_METRIC_INGEST_TOKEN`. Every value requires explicit source, observation time and freshness. A null value is forced to `UNKNOWN`; the endpoint does not infer revenue or customers from product activity.

Founder-authenticated diagnostics include:

- `/api/readiness` — configuration readiness only, never credential values;
- `/api/companies/<company_id>/sources` — provenance/freshness inventory;
- `/api/companies/<company_id>/history` — bounded read window over immutable state snapshots;
- `/api/audit` — recent action/evidence-ingestion audit events.

## Security and authority status

`FCC_ADMIN_TOKEN`, `FCC_SESSION_SECRET`, Factory/metric ingest tokens and optional GitHub credentials remain server-side. Founder session mutations require CSRF validation. Missing required private-session configuration fails closed.

Health checks reject localhost/private/non-global destinations and do not automatically follow arbitrary redirects. Deployment metadata cannot silently grant health-check authority to an unsafe environment URL.

2FA/IdP integration remains `UNKNOWN / NOT CONNECTED`. Production deployment, merge, billing changes, external communications, destructive data operations and irreversible commitments remain owner-controlled and are not executed by this MVP.
