# Factory Cloud external runtime

This directory contains host-side artifacts for the owner-authorized **isolated, non-production** Factory Cloud runtime. They do not imply that a host has been provisioned or that 24/7 execution is active.

## Process adapter contract

Each repository-safe application worker can be given an external JSON config via `--adapter-config`. The config contains only app identity, mode, workspace path, executable argv and timeout. Do not put credentials, customer data, billing authority or production secrets in the JSON file.

The app-owned executable receives one `ExecutionRequest` JSON object on stdin. It must emit exactly one JSON object on stdout with a terminal status (`DONE`, `WAIT`, `BLOCKED`, `ERROR`) plus metadata-only baton fields. Raw stdout/stderr is discarded by Factory Cloud. Only a narrow evidence allowlist is persisted.

Before the executable runs, the worker independently checks `git rev-parse HEAD` inside the configured workspace and requires exact equality with the execution-source head already verified by the control plane. A stale/unverifiable workspace fails closed.

`app-adapter.example.json` remains the generic example. `obrasignal-adapter.json` is now a concrete non-secret configuration for the built-in ObraSignal verification agent.

## Concrete ObraSignal host path

The built-in ObraSignal adapter expects:

- application workspace: `/srv/factory-cloud/apps/obrasignal`;
- Factory Cloud control-plane checkout: `/opt/factory-cloud/current`;
- concrete executable: `/usr/bin/python3 /opt/factory-cloud/current/factory_cloud/obrasignal_agent.py`.

`systemd/prepare-obrasignal-workspace.sh` reads the **verified execution-source branch and SHA** from `factory_cloud/apps.json` (falling back to canonical source only when no separate execution source is registered), creates a private development checkout when absent, refuses to move a dirty existing workspace, fetches the registered branch, and checks out the registered SHA detached. It does not reset/clean a dirty checkout and does not touch K3.

The concrete agent supports `verify:execution:compile`, `verify:execution:python`, `verify:execution:mobile`, and `verify:execution:quality`. It accepts no arbitrary shell task. `verify:execution:compile` requires only the configured Python interpreter and is the registry's first host-acceptance BATON item. Mobile verification deliberately requires pre-existing `mobile/node_modules`; it never installs dependencies itself. Python tooling may be selected in the isolated worker environment with `FACTORY_CLOUD_OBRASIGNAL_PYTHON`; no such path is persisted in shared Factory Cloud state.

## systemd topology

- `factory-cloud-control.service`: one durable control-plane dispatcher.
- `factory-cloud-app@.service`: one private OS user/group per app plus membership in the shared `factory-cloud` metadata group.
- `factory-cloud.target`: groups the services.
- `systemd/install.sh`: host-side provisioning helper. By default it provisions only `obrasignal`, installs the built-in adapter config into the private app group, prepares the exact ObraSignal development checkout, then starts the services. Additional apps still require their own safe adapter/config and source authority.

The state directory is setgid `2770` and both service types use `UMask=0007`, so SQLite/WAL/SHM files remain writable by the shared metadata group without giving app workers a shared primary identity. App config files are `root:factory-cloud-<app>` mode `0640`; app secret environment files should use the same private app group and must never be readable by the shared `factory-cloud` group.

The app workspace and app executable remain outside shared orchestration state. Give each app OS user access only to its own development workspace and credentials. Do not mount production databases or shared secret stores into Factory Cloud.

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
2. each enabled app worker is active under its own OS user;
3. `/var/lib/factory-cloud/state.sqlite3` survives process restarts and remains writable through WAL/SHM creation by both control and app worker processes;
4. killing/restarting the control service records interruption/recovery without duplicate dispatch;
5. killing/restarting an app worker allows an expired app-scoped job claim to be reclaimed;
6. ObraSignal workspace HEAD exactly matches the independently verified execution-source head (or canonical head only when no separate execution source is registered);
7. ObraSignal concrete adapter successfully executes the seeded `verify:execution:compile` task and persists metadata-only evidence;
8. ObraSignal adapter refuses a stale local HEAD and refuses a non-allowlisted task;
9. K3 remains without a repository-mutating process adapter until canonical source truth is independently verified.

Until those checks pass on a real external host, do **not** describe Factory Cloud as 24/7 autonomous execution.
