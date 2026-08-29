# Global Control Tower host runbook

Purpose: run one persistent Control Tower for every registered Factory without founder-entered per-Factory chat URLs.

## Topology

```text
Founder UI
  -> same-origin proxy (recommended)
    -> Global Control Tower :8787
      -> Factory Cloud app orchestrator for app-development routes
      -> ONE shared portfolio-agent runtime :8788 for business/specialist routes
        -> ONE actual agent executor
```

Factory identity, canonical internal route, signal and BATON travel in the request. No per-Factory chat URL or executable path exists.

## Host requirements

- persistent filesystem at `/var/lib/factory-cloud` or another absolute runtime directory
- long-lived process/container with automatic restart
- HTTPS termination before public exposure
- `FACTORY_CONTROL_TOKEN` is mandatory for any non-local Control Tower bind
- `FACTORY_CONTROL_ALLOWED_ORIGIN` set to the exact Founder UI origin when cross-origin browser access is used
- exactly one shared portfolio runtime: executable OR HTTPS endpoint
- no customer production DBs, billing credentials, app-production secrets or cross-company production authority in the Control Tower

## Control Tower container

The image binds `0.0.0.0:8787`, so it intentionally refuses to start without a Control Tower token.

```sh
docker build -f factory_cloud/Dockerfile.control-tower -t factory-control-tower .
docker run --rm \
  -p 8787:8787 \
  -v factory-control-state:/var/lib/factory-cloud \
  -e FACTORY_CONTROL_TOKEN='<control-tower-secret>' \
  factory-control-tower
```

`GET /health` proves the HTTP process is alive. `GET /ready` is stricter: it stays 503 while the portfolio execution runtime is absent or unverified, so configuration is never presented as proven execution readiness.

## Shared portfolio-agent runtime

A concrete authenticated service boundary now exists in `factory_cloud.portfolio_agent_service`. It accepts all portfolio Factories through one endpoint, validates Factory/route identity, and invokes one actual executor through JSON stdin without shell interpolation.

```sh
docker build -f factory_cloud/Dockerfile.portfolio-agent -t factory-portfolio-agent .
docker run --rm \
  -p 8788:8788 \
  -e FACTORY_PORTFOLIO_AGENT_TOKEN='<agent-secret>' \
  -e FACTORY_PORTFOLIO_AGENT_EXECUTOR='/opt/agent/portfolio-agent' \
  -v /host/path/to/portfolio-agent:/opt/agent/portfolio-agent:ro \
  factory-portfolio-agent
```

Then point the Control Tower at the one shared endpoint:

```sh
FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT=https://agent.example.com/v1/execute
FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN=<agent-secret>
```

For a same-host private connection, localhost HTTP is allowed. Remote HTTP is rejected; remote endpoints require HTTPS and the host-level token.

Do not configure both a local `FACTORY_CLOUD_PORTFOLIO_WORKER` executable and `FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT`.

## Control Tower API protection

For remote use:

```sh
FACTORY_CONTROL_TOKEN=<control-tower-secret>
FACTORY_CONTROL_ALLOWED_ORIGIN=https://founder-control-center-preview.vercel.app
```

Prefer the supplied same-origin Founder proxy so the browser never contains the Control Tower bearer token. Do not embed either Control Tower or agent tokens in static HTML or JavaScript.

## Founder commands and automatic paths

- `GET /v1/routes` returns the current automatic route manifest for every canonical Factory and the alias map.
- `POST /v1/dispatch` accepts `all`, `obrasignal`, `obrasignal-subs`, `business`, `development`, or one canonical/historical alias Factory ID.
- `GET /v1/batches/<batch_id>` returns persisted per-Factory execution truth.
- historical `changeledger` resolves to canonical `scopeledger`; it is not dispatched twice.

## Acceptance gate

1. exact-head Python + Mobile CI GREEN
2. persistent state survives host restart
3. one command dispatches multiple Factory routes
4. one blocked Factory does not stop other eligible routes
5. no per-Factory chat URL/path exists
6. no false RUNNING state
7. worker and agent cannot spoof Factory/route identity or unsupported status
8. non-local Control Tower bind without auth is rejected before startup
9. remote worker and remote Control Tower are authenticated
10. automatic route manifest covers every registered canonical Factory
11. Founder UI points to the real single endpoint/proxy
12. actual agent executor proves at least one real Factory operation before runtime is classified operational

The repository acceptance suite includes a full synthetic HTTP path: one Control Tower business command -> one shared authenticated portfolio-agent endpoint -> multiple Factory results -> one local blocker while the rest complete -> persisted batch survives dispatcher restart. This proves orchestration plumbing only; it does **not** prove that a real autonomous AI/tool executor is provisioned.

Until the actual executor and persistent host pass the final gates, classify external business-Factory execution as NOT_PROVISIONED / WAIT.
