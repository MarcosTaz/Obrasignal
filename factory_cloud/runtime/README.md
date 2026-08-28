# Factory Cloud external runtime

This directory contains host-side artifacts for the owner-authorized **isolated, non-production** Factory Cloud runtime. They do not imply that a host has been provisioned or that 24/7 execution is active.

## Process adapter contract

Each repository-safe application worker can be given an external JSON config via `--adapter-config`. The config contains only app identity, mode, workspace path, executable argv and timeout. Do not put credentials, customer data, billing authority or production secrets in the JSON file.

The app-owned executable receives one `ExecutionRequest` JSON object on stdin. It must emit exactly one JSON object on stdout with a terminal status (`DONE`, `WAIT`, `BLOCKED`, `ERROR`) plus metadata-only baton fields. Raw stdout/stderr is discarded by Factory Cloud. Only a narrow evidence allowlist is persisted.

Before the executable runs, the worker independently checks `git rev-parse HEAD` inside the configured workspace and requires exact equality with the canonical head already verified by the control plane. A stale/unverifiable workspace fails closed.

Example config: `app-adapter.example.json`.

## systemd topology

- `factory-cloud-control.service`: one durable control-plane dispatcher.
- `factory-cloud-app@.service`: one OS user/process per app, sharing only the metadata SQLite group boundary.
- `factory-cloud.target`: groups the services.
- `systemd/install.sh`: host-side provisioning helper. It requires external per-app adapter configs before starting workers.

The app workspace and app executable are intentionally outside the shared repository/runtime configuration. Give each app OS user access only to its own development workspace and credentials. Do not mount production databases or shared secret stores into Factory Cloud.

## Activation/verification gate

A host is not considered provisioned until all of the following have been observed on that host:

1. control service is active and owns the dispatch lease;
2. each enabled app worker is active under its own OS user;
3. `/var/lib/factory-cloud/state.sqlite3` survives process restarts;
4. killing/restarting the control service records interruption/recovery without duplicate dispatch;
5. killing/restarting an app worker allows an expired app-scoped job claim to be reclaimed;
6. ObraSignal adapter refuses a stale local HEAD;
7. K3 remains without a repository-mutating process adapter until canonical source truth is independently verified.

Until those checks pass on a real external host, do **not** describe Factory Cloud as 24/7 autonomous execution.
