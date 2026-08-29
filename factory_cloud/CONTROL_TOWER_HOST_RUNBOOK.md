# Global Control Tower host runbook

Purpose: run one persistent Control Tower service for all registered Factories without founder-entered per-Factory chat URLs.

## Required host properties

- persistent filesystem mounted at `/var/lib/factory-cloud` (or another absolute path supplied to `--runtime-dir`)
- one long-lived process/container restarted automatically by the host
- HTTPS termination in front of the HTTP service
- private environment/configuration for the single shared portfolio worker when provisioned
- no customer production databases, billing credentials, app production secrets, or cross-app production authority in this service

## Container

Build from repository root:

```sh
docker build -f factory_cloud/Dockerfile.control-tower -t factory-control-tower .
```

Run with durable state:

```sh
docker run --rm \
  -p 8787:8787 \
  -v factory-control-state:/var/lib/factory-cloud \
  factory-control-tower
```

Health probe:

```sh
curl -fsS http://127.0.0.1:8787/health
```

Expected response includes `{"ok": true, "service": "global-control-tower"}`.

## Portfolio worker

Business/portfolio Factories intentionally remain WAIT until one shared worker is provisioned. Configure only one host-level executable path:

```sh
FACTORY_CLOUD_PORTFOLIO_WORKER=/absolute/path/to/shared-portfolio-worker
```

The Control Tower sends Factory identity, route, signal, mission and BATON as JSON over stdin. There is no per-Factory executable path and no per-Factory ChatGPT/conversation URL.

## Founder UI

The Founder Control UI sends one POST request to `/v1/dispatch` with scopes such as:

- `all`
- `obrasignal`
- `obrasignal-subs`
- `business`
- `development`

It then reads `/v1/batches/<batch_id>` for execution truth. WAIT/BLOCKED/ERROR are preserved per Factory; the UI must never infer RUNNING from a copied signal or opened browser tab.

## Acceptance gate before production use

1. exact-head CI GREEN
2. persistent state survives host restart
3. one command dispatches multiple Factories through derived internal routes
4. one blocked Factory does not prevent independent eligible Factory results
5. no per-Factory chat URL/path is required
6. no false RUNNING state
7. Founder UI points to the real HTTPS Control Tower endpoint

Until these are proven on the actual host, classify the external runtime as NOT_PROVISIONED / WAIT.
