# Factory Cloud — Application Development Control Plane

Factory Cloud is orchestration infrastructure above registered applications. It is not ObraSignal, K3 Fatality, or a business/research Factory.

## Runtime topology

1. `factory_cloud.worker` is the control-plane host. It loads `apps.json`, acquires the durable dispatch lease, recovers interrupted BATON state, verifies current source truth where supported, chooses safe work, and hands repository-safe jobs to a **physically separate durable queue per app**.
2. `factory_cloud.app_worker` is restricted to one `app_id` and requires an explicit private `--queue` SQLite path. Separate processes are hosted with separate OS users, groups, credentials and environments. With no configured process adapter it remains fail-closed. A repository-safe app can inject an app-owned executable through `--adapter-config`.
3. `factory_cloud.process_adapter` is the process boundary between a queued Factory Cloud job and an application-specific execution agent. It independently verifies the configured local workspace HEAD before invocation, uses argv without a shell, accepts only a bounded JSON result contract and never persists raw stdout/stderr.
4. `factory_cloud.obrasignal_agent` is the first concrete application-specific agent. It is deliberately non-mutating and supports only an explicit ObraSignal verification task allowlist; it is not a general shell or an LLM coding agent.
5. The global SQLite database stores control-plane orchestration metadata only: BATON/checkpoints, leases and execution history. Worker-job envelopes/results are stored in per-app queue databases under the app's private queue directory. None of these databases is an application production database.

The control-plane process and each app worker may be restarted. Global BATON state is recovered from the durable control database. A dispatch lease prevents two control-plane hosts from dispatching simultaneously. Each app queue has app-scoped claims with expiries so an abandoned job can be reclaimed after a worker crash without exposing another app's queue.

## Example foreground processes

```bash
python -m factory_cloud.worker Ω \
  --state /var/lib/factory-cloud/state.sqlite3 \
  --queue-dir /var/lib/factory-cloud/queues

python -m factory_cloud.app_worker Ω \
  --app-id obrasignal \
  --queue /var/lib/factory-cloud/queues/obrasignal/queue.sqlite3 \
  --adapter-config /etc/factory-cloud/apps/obrasignal.json
```

An app worker no longer accepts the global control-plane state database as its job transport. The explicit queue path is required. With no `--adapter-config`, repository-safe workers intentionally retain `WAIT / repository_tooling_adapter_required`. A process adapter config is allowed only for `repository_safe_execution`; it cannot be used to bypass K3's unresolved-source boundary.

Host-side systemd templates and the provisioning helper live under `factory_cloud/runtime/`. They are deployment artifacts, not proof that an external host is running. Keeping Factory Cloud alive across machine/process failure still requires those services to be provisioned and acceptance-tested on a real isolated host.

## Concrete ObraSignal executor

`factory_cloud.obrasignal_agent` currently accepts exactly these tasks:

- `verify:canonical:compile` — dependency-free root Python syntax compilation, suitable as the first host acceptance dispatch;
- `verify:canonical:python` — compile root Python modules and run the repository Python test contract;
- `verify:canonical:mobile` — run Expo Doctor and the existing mobile smoke contracts only when `mobile/node_modules` is already present;
- `verify:canonical:quality` — run Python verification and then mobile verification.

Task text is never interpolated into a command. The agent uses fixed argv, no shell, performs its own defense-in-depth local HEAD check, captures subprocess output without returning it, and emits metadata-only evidence. Unsupported tasks WAIT rather than being interpreted as commands.

The agent does **not** install mobile dependencies, modify source files, create branches, commit, merge, deploy, activate sources/providers, access billing, or communicate externally. Dependency/tool preparation belongs to the isolated app workspace/worker environment. This closes a concrete execution-adapter gap for safe verification work; it does not yet provide autonomous code-authoring capability.

The built-in non-secret runtime config is `factory_cloud/runtime/obrasignal-adapter.json`. It points the app worker at `/srv/factory-cloud/apps/obrasignal` and the control-plane copy of the concrete agent. The host installer can copy that config into the private per-app config group and prepare the development checkout at the exact verified canonical SHA recorded in `apps.json`.

The registry now seeds ObraSignal with `verify:canonical:compile` as the first executable BATON item, followed by deeper Python/mobile verification. Once those allowlisted tasks are exhausted, source-mutating/code-authoring work remains an explicit WAIT boundary until a separately verified repository-safe coding adapter exists.

## App process contract

The external app executable receives one `ExecutionRequest` JSON object on stdin and returns one metadata-only JSON object on stdout. Supported terminal statuses are `DONE`, `WAIT`, `BLOCKED` and `ERROR`. Raw stdout/stderr is discarded. Persisted evidence is restricted to a narrow allowlist (`commit_sha`, `verified_head`, `test_state`, `task_state`, `evidence_codes`) plus Factory Cloud-generated adapter/head metadata.

The app worker performs an independent `git rev-parse HEAD` check in the configured workspace and requires exact equality with the request's canonical head before the external process can run. This is in addition to the control plane's live GitHub branch-head verification before queue dispatch. The ObraSignal agent repeats that HEAD comparison before its allowlisted verification commands.

Adapter JSON files must not contain credentials, customer data, billing authority, deployment authority or production secrets. App-specific credentials belong only to the isolated worker process environment.

## Source truth

For registered GitHub applications, the control-plane runtime performs a read-only branch-head check before queue dispatch. If live verification is unavailable, source truth is incomplete, or the observed head differs from the registered canonical head, dispatch fails closed to WAIT. An optional `FACTORY_CLOUD_GITHUB_TOKEN` may be supplied by the process environment for GitHub API access; it is never persisted by Factory Cloud.

K3 Fatality remains `read_only_until_source_resolved`. Runtime existence is not repository authority. No K3 repository mutation may be dispatched until canonical source truth is established, and process-adapter configuration rejects non-`repository_safe_execution` modes.

## Isolation boundary

Every app keeps its own repository, credentials, secrets, application database, production environment, billing/provider authority, customer data, deployment authority, rollback path **and worker queue database**. The control plane may share only global metadata/BATON state, scheduling and read-only verification; app worker processes do not receive filesystem access to that global control database.

Runtime defense is layered:

- one SQLite queue file and parent directory per `app_id`;
- queue paths validate `app_id` and reject traversal-like identifiers;
- the queue API rejects cross-app submit/claim/enumeration/finish operations when physically scoped;
- one Unix user/group per app, with no membership in the shared control metadata group;
- per-app queue directories are group-accessible only to the corresponding worker identity and the control owner;
- the systemd app unit grants write access only to `/var/lib/factory-cloud/queues/%i` and masks the global `state.sqlite3` path.

The installer fails closed if it detects the legacy shared `factory-cloud` supplementary group on an app user. It also refuses the queue-layout migration while the legacy shared `worker_jobs` table contains an unconsumed job, preventing silent loss/replay of in-flight work.

Never place app secrets or customer data in `state.sqlite3`, per-app queue SQLite files, `apps.json`, adapter config/result metadata, execution evidence or worker-job payloads.

## Safety boundary

Factory Cloud never grants automatic authority to merge main, deploy production, mutate production data, rotate secrets, activate billing/providers, send external communications or perform irreversible actions. Those become WAIT boundaries while independent safe work continues.

A repository-safe process adapter is not equivalent to production authority. The host must not give an app worker production credentials merely because that worker can execute repository-safe development tooling.

## 24/7 truth gate

Do not claim 24/7 autonomous execution until an external host/process manager has actually been provisioned and verified with durable state, restart/takeover acceptance, app-worker claim recovery, independent app OS identities, private per-app queues and the source-truth gates above. The exact acceptance checklist is in `factory_cloud/runtime/README.md`.
