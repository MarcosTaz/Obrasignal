# Global Control Tower host runbook

Purpose: run one persistent Control Tower for every registered Factory without founder-entered per-Factory chat URLs.

## Host requirements

- persistent filesystem at `/var/lib/factory-cloud` or another absolute runtime directory
- long-lived process/container with automatic restart
- HTTPS termination before public exposure
- `FACTORY_CONTROL_TOKEN` is mandatory for any non-local bind (`0.0.0.0`, public/private interface, container exposure)
- `FACTORY_CONTROL_ALLOWED_ORIGIN` set to the exact Founder UI origin when cross-origin browser access is used
- exactly one shared portfolio runtime: executable OR HTTPS endpoint
- no customer production DBs, billing credentials, app-production secrets or cross-company production authority in the Control Tower

## Container

The image binds `0.0.0.0:8787`, so it intentionally refuses to start without a Control Tower token.

```sh
docker build -f factory_cloud/Dockerfile.control-tower -t factory-control-tower .
docker run --rm \
  -p 8787:8787 \
  -v factory-control-state:/var/lib/factory-cloud \
  -e FACTORY_CONTROL_TOKEN='<control-tower-secret>' \
  factory-control-tower
```

Health remains readable for host/load-balancer probes:

```sh
curl -fsS http://127.0.0.1:8787/health
```

Execution API requires the bearer token:

```sh
curl -fsS \
  -H 'Authorization: Bearer <control-tower-secret>' \
  -H 'Content-Type: application/json' \
  -d '{"scope":"all"}' \
  http://127.0.0.1:8787/v1/dispatch
```

## One shared portfolio runtime

Local executable:

```sh
FACTORY_CLOUD_PORTFOLIO_WORKER=/absolute/path/to/shared-portfolio-worker
```

or remote HTTPS worker:

```sh
FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT=https://worker.example.com/v1/execute
FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN=<host-level-secret>
```

Do not configure both. A remote endpoint without HTTPS or without the host-level token fails closed. The worker receives Factory identity, route, signal, mission and BATON in one payload; there is no per-Factory URL/path.

## Control Tower API protection

For remote use:

```sh
FACTORY_CONTROL_TOKEN=<control-tower-secret>
FACTORY_CONTROL_ALLOWED_ORIGIN=https://founder-control-center-preview.vercel.app
```

Prefer a same-origin server-side proxy so the Founder browser never contains the Control Tower bearer token. Do not embed the token in static HTML or JavaScript.

## Founder commands

`POST /v1/dispatch` with `scope` equal to `all`, `obrasignal`, `obrasignal-subs`, `business`, `development`, or a canonical Factory ID. Read `GET /v1/batches/<batch_id>` for execution truth.

## Acceptance gate

1. exact-head Python + Mobile CI GREEN
2. persistent state survives host restart
3. one command dispatches multiple Factory routes
4. one blocked Factory does not stop other eligible routes
5. no per-Factory chat URL/path exists
6. no false RUNNING state
7. worker cannot spoof Factory/route identity or unsupported status
8. non-local Control Tower bind without auth is rejected before startup
9. remote worker and remote Control Tower are authenticated
10. Founder UI points to the real single endpoint/proxy

Until the actual host and agent runtime pass this gate, classify external execution as NOT_PROVISIONED / WAIT.
