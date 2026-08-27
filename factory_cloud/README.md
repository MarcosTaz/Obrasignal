# Factory Cloud — Application Development Control Plane

Factory Cloud is orchestration infrastructure above registered applications. It is not ObraSignal, K3 Fatality, or a business/research Factory.

## Runtime topology

1. `factory_cloud.worker` is the control-plane host. It loads `apps.json`, acquires the durable dispatch lease, recovers interrupted BATON state, verifies current source truth where supported, chooses safe work, and hands repository-safe jobs to the durable app-worker queue.
2. `factory_cloud.app_worker` is restricted to one `app_id`. Separate processes may be hosted with separate credentials/environments. The default adapter is deliberately fail-closed; real app tooling must be injected in that app worker's own environment.
3. SQLite stores orchestration metadata only: BATON/checkpoints, leases, execution history and worker-job envelopes/results. It is not a shared application database.

The control-plane process and each app worker may be restarted. State is recovered from the durable SQLite checkpoint. A dispatch lease prevents two control-plane hosts from dispatching simultaneously. App jobs use app-scoped claims with expiries so an abandoned job can be reclaimed after a worker crash.

## Example foreground processes

```bash
python -m factory_cloud.worker Ω --state /var/lib/factory-cloud/state.sqlite3
python -m factory_cloud.app_worker Ω --app-id obrasignal --state /var/lib/factory-cloud/state.sqlite3
```

These commands run foreground processes. Keeping them alive across machine/process failure requires an external process manager or worker platform. This repository does **not** provision that host and does not imply that ChatGPT continues running after a turn ends.

## Source truth

For registered GitHub applications, the control-plane runtime performs a read-only branch-head check before queue dispatch. If live verification is unavailable, source truth is incomplete, or the observed head differs from the registered canonical head, dispatch fails closed to WAIT. An optional `FACTORY_CLOUD_GITHUB_TOKEN` may be supplied by the process environment for GitHub API access; it is never persisted by Factory Cloud.

K3 Fatality remains `read_only_until_source_resolved`. Runtime existence is not repository authority. No K3 repository mutation may be dispatched until canonical source truth is established.

## Isolation boundary

Every app keeps its own repository, credentials, secrets, application database, production environment, billing/provider authority, customer data, deployment authority and rollback path. Factory Cloud may share only metadata, BATON state, scheduling, safe task envelopes, evidence references and read-only verification.

Never place app secrets or customer data in `factory_cloud_state.sqlite3`, `apps.json`, execution evidence or worker-job payloads.

## Safety boundary

Factory Cloud never grants automatic authority to merge main, deploy production, mutate production data, rotate secrets, activate billing/providers, send external communications or perform irreversible actions. Those become WAIT boundaries while independent safe work continues.

A repository-safe adapter is not equivalent to production authority. Default adapters intentionally return WAIT rather than pretending external work happened.
