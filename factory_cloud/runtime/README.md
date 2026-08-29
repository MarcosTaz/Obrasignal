# Factory Cloud external runtime

This directory contains host-side artifacts for the owner-authorized **isolated, non-production** Factory Cloud runtime. They do not imply that a host has been provisioned or that 24/7 execution is active.

## Process adapter contract

Each repository-safe application worker can be given an external JSON config via `--adapter-config`. The config contains only app identity, mode, workspace path, executable argv and timeout. Do not put credentials, customer data, billing authority or production secrets in the JSON file.

The app-owned executable receives one `ExecutionRequest` JSON object on stdin. It must emit exactly one JSON object on stdout with a terminal status (`DONE`, `WAIT`, `BLOCKED`, `ERROR`) plus metadata-only baton fields. Raw stdout/stderr is discarded by Factory Cloud. Only a narrow evidence allowlist is persisted.

Before the executable runs, the worker independently checks `git rev-parse HEAD` inside the configured workspace and requires exact equality with the canonical head already verified by the control plane. A stale/unverifiable workspace fails closed.

`app-adapter.example.json` remains the generic example. `obrasignal-adapter.json` is now a concrete non-secret configuration for the built-in ObraSignal verification agent.

## Concrete ObraSignal host path

The built-in ObraSignal adapter expects:

- application workspace: `/srv/factory-cloud/apps/obrasignal`;
- Factory Cloud control-plane checkout: `/opt/factory-cloud/current`;
- concrete executable: `/usr/bin/python3 /opt/factory-cloud/current/factory_cloud/obrasignal_agent.py`.

`systemd/prepare-obrasignal-workspace.sh` reads the **verified canonical SHA** from `factory_cloud/apps.json`, creates a private development checkout when absent, refuses to move a dirty existing workspace, fetches the registered execution branch, and checks out the registered SHA detached. It does not reset/clean a dirty checkout and does not touch K3.

The concrete agent supports `verify:canonical:compile`, `verify:canonical:python`, `verify:canonical:mobile`, and `verify:canonical:quality`. It accepts no arbitrary shell task. `verify:canonical:compile` requires only the configured Python interpreter and is the registry's first host-acceptance BATON item. Mobile verification deliberately requires pre-existing `mobile/node_modules`; it never installs dependencies itself. Python tooling may be selected in the isolated worker environment with `FACTORY_CLOUD_OBRASIGNAL_PYTHON`; no such path is persisted in Factory Cloud state or queues.

## systemd topology

- `factory-cloud-control.service`: one durable control-plane dispatcher. It alone opens `/var/lib/factory-cloud/state.sqlite3`, and dispatches jobs through `/var/lib/factory-cloud/queues/<app>/queue.sqlite3`.
- `factory-cloud-app@.service`: one private OS user/group per app. It opens only `/var/lib/factory-cloud/queues/%i/queue.sqlite3`; the global state database is masked from the worker service.
- `factory-cloud.target`: groups the services.
- `systemd/install.sh`: host-side provisioning helper. By default it provisions only `obrasignal`, installs the built-in adapter config into the private app group, prepares the exact ObraSignal development checkout, then starts the services. Additional apps still require their own safe adapter/config and source authority.

App workers must **not** belong to the shared `factory-cloud` control metadata group. Fresh installs create only their app-specific group identity. The installer fails closed if a pre-existing worker still has legacy `factory-cloud` supplementary membership.

The trusted `factory-cloud-control` user is added to every enabled app's private queue group. This is intentionally one-way: control can open every queue, but each worker belongs only to its own app group. That remains correct even if a worker, rather than control, creates `queue.sqlite3` or its WAL/SHM files first.

The queue root is not listable by app workers. Each per-app queue directory is owned by `factory-cloud-control`, grouped to `factory-cloud-<app>`, and setgid `2770`; SQLite/WAL/SHM files therefore remain accessible to the trusted control process and that app worker without becoming readable by another app identity. The app systemd unit additionally limits write access to its private queue directory and masks the global state database paths.

App config files are `root:factory-cloud-<app>` mode `0640`; app secret environment files should use the same private app group and must never be readable by another app or by a shared metadata group.

The app workspace and app executable remain outside orchestration state. Give each app OS user access only to its own development workspace and credentials. Do not mount production databases or shared secret stores into Factory Cloud.

## Queue-layout migration gate

Older Factory Cloud builds stored `worker_jobs` in the global `state.sqlite3`. The current runtime does not use that table for new dispatches. Before changing layouts, `install.sh` opens the legacy database read-only and refuses migration if any legacy job has `consumed_at IS NULL`. This prevents an unfinished or completed-but-unconsumed result from being silently abandoned or replayed.

If the installer reports legacy shared-group membership or unconsumed legacy jobs, it stops before service restart. Those conditions must be explicitly classified/remediated on the authorized host; the installer does not erase jobs, force-consume results, reset repositories or silently rewrite identities.

## Host preparation

On an explicitly authorized isolated Linux host, after placing the Factory Cloud branch at `/opt/factory-cloud/current`:

```bash
sudo bash /opt/factory-cloud/current/factory_cloud/runtime/systemd/install.sh
```

The default install path prepares ObraSignal only. `PREPARE_WORKSPACES=0` can be used to install service/config artifacts without moving or cloning an app workspace. The preparer fails closed on unverified registry truth, dirty workspace state, unavailable registered commit, or final HEAD mismatch.

This installer does **not** install ObraSignal Python/mobile dependencies, create production credentials, grant deployment authority, or activate providers. The dependency-free compile task can run without pytest/npm; deeper Python/mobile verification requires its app-specific toolchain to be prepared separately under the app-specific OS identity. Missing mobile dependencies cause the concrete agent to WAIT instead of installing them.

## Activation/verification gate

A host is not considered provisioned until all of the following have been observed on that host:

1. control service is active and owns the dispatch lease;
2. each enabled app worker is active under its own OS user/group and has no shared `factory-cloud` supplementary membership;
3. the trusted control user can open every private app queue even when the corresponding worker creates SQLite/WAL/SHM first;
4. `/var/lib/factory-cloud/state.sqlite3` survives control-process restarts while app workers cannot open it;
5. each enabled app has a distinct `/var/lib/factory-cloud/queues/<app>/queue.sqlite3`, and a worker cannot list/open another app's queue directory;
6. killing/restarting the control service records interruption/recovery without duplicate dispatch;
7. killing/restarting an app worker allows an expired claim in that app's private queue to be reclaimed;
8. ObraSignal workspace HEAD exactly matches independently verified source truth;
9. ObraSignal concrete adapter successfully executes the seeded `verify:canonical:compile` task and persists metadata-only evidence;
10. ObraSignal adapter refuses a stale local HEAD and refuses a non-allowlisted task;
11. a two-app adversarial acceptance run proves one worker cannot consume, finish, enumerate, mutate HEAD/BATON for, or filesystem-open the other app's queue/state;
12. K3 remains without a repository-mutating process adapter until canonical source truth is independently verified.

Until those checks pass on a real external host, do **not** describe Factory Cloud as 24/7 autonomous execution.
