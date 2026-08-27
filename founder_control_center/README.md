# Founder Control Center

Private, fail-closed control plane for the founder portfolio.

## Invariants

- `UNKNOWN != GREEN`
- stale evidence invalidates previously trusted operational states
- dashboard state never replaces source-of-truth systems
- every material status carries source/freshness metadata
- RED actions never execute autonomously
- YELLOW actions prepare only and require founder approval
- GREEN actions are read-only or internal/non-destructive
- no credentials are exposed to the browser

## Current MVP

- private founder authentication with stable server-side session secret
- CSRF protection for founder mutations and hardened response headers
- normalized Company Manifest model for current and future companies
- all known portfolio items visible from first boot
- ACTIVE / NEXT / WAIT per company and source-aware Factory feeds
- CEO attention ranking with explicit uncertainty and escalation for degraded CI/deployment/health
- central highest-value Action Center
- GREEN / YELLOW / RED enforcement
- persistent SQLite registry and audit history
- read-only GitHub repository, CI and deployment adapters
- application health adapter
- canonical server-to-server business metric feed for revenue, pipeline and customers
- normalized per-company APIs for metrics, Factory state, risks, revenue and actions
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

The container defaults to a single Gunicorn worker and `FCC_DB=/data/founder_control_center.db`. Mount `/data` on persistent storage for durable audit/registry state. This SQLite topology is intentionally single-instance; horizontal scaling requires a canonical shared database before replicas can be trusted.

## Tests

```bash
python -m unittest discover -s founder_control_center/tests -v
```

The dedicated pull-request workflow also builds the container image.

## Live integrations

Public GitHub repositories can be refreshed read-only without credentials. Set `FCC_GITHUB_TOKEN` to enable private-repository truth and improve API allowance. An inaccessible repository remains `UNKNOWN`.

GitHub deployment status is a separate evidence channel from repository CI. Application health is separate again: HTTP/process health does not prove business correctness.

Factories can push only their own `ACTIVE / NEXT / WAIT` state through `/api/ingest/factory-state` using the separate `FCC_FACTORY_INGEST_TOKEN`. A Factory feed cannot overwrite global company truth.

Canonical billing/CRM adapters can push only `revenue`, `pipeline` or `customers` through `/api/ingest/business-metric` using `FCC_METRIC_INGEST_TOKEN`. Every value requires explicit source, observation time and freshness. A null value is forced to `UNKNOWN`; the endpoint does not infer revenue or customers from product activity.

## Security and authority status

`FCC_ADMIN_TOKEN`, `FCC_SESSION_SECRET`, Factory/metric ingest tokens and optional GitHub credentials remain server-side. Founder session mutations require CSRF validation. Missing required private-session configuration fails closed.

2FA/IdP integration remains `UNKNOWN / NOT CONNECTED`. Production deployment, billing changes, external communications, destructive data operations and irreversible commitments remain owner-controlled and are not executed by this MVP.
