# Engineering Operations & Orchestration

This is a **non-authoritative operational metadata layer**. It automates the
flow of exact repository evidence between owners. It does not create product
truth and it cannot authorize merge, release, deployment, queue/capability
promotion, source activation, production mutation, secrets/config changes, or
specialist decisions.

## First automation slice

`engineering_ops_github.py` observes GitHub using GET requests only and emits:

- `engineering-ops-status.json` — machine-readable `engineering-ops.v1`;
- `engineering-ops-status.md` — bounded human-readable drift report.

The collector inventories open PR exact HEAD/base/main metadata, explicit
PR-to-SHA dependencies in PR bodies, mergeability when GitHub exposes it, and
workflow runs on each current PR HEAD. The normalization layer then:

1. compares a declared PR-body HEAD with the actual PR HEAD;
2. compares a declared main SHA with canonical main;
3. resolves explicit `#PR -> SHA` handoff pins against the referenced PR's
   current HEAD;
4. records successful workflow runs on a different SHA as `HISTORICAL` /
   `STALE`, never current PASS;
5. records skipped/path-filtered exact-head runs as `NOT_RUN`, not RED;
6. degrades missing or failed collection to `UNKNOWN / NEEDS_RECHECK`.

Historical evidence is not deleted.

## Status contract

The machine-readable contract is `engineering_ops_manifest.json`. Every
candidate record contains:

`owner`, `exact_head`, `base`, `main_sha`, `evidence`, `reason`,
`reopen_condition`.

`owner` remains `UNKNOWN` until an explicit owner directory or owner-authored
contract can resolve it; repository authorship is not treated as domain
ownership.

The status vocabulary is bounded to:

`ACTIVE`, `NEXT`, `WAIT`, `GREEN`, `RED`, `STALE`, `BLOCKED_EXTERNAL`,
`BLOCKED_OWNER`, `READY`, `HANDOFF_READY`, `CANONICAL_NEXT`, `SUPERSEDED`,
`UNKNOWN`.

This first slice deliberately emits only `ACTIVE`, `STALE`, or `UNKNOWN`.
It does not infer `GREEN`, `READY`, `HANDOFF_READY`, or `CANONICAL_NEXT`.
Those require authoritative owner/Quality/Integration/Golden/Assembly inputs
that later orchestration slices may consume but never redefine.

## Evidence safety

- `UNKNOWN != GREEN`
- `STALE != FAILED`
- `NOT_RUN != RED`
- historical green != current proof
- current operational references != product readiness
- green workflow != merge authorization

A collector/classifier failure writes an `UNKNOWN` report before failing the
workflow. Finding stale evidence itself does **not** fail the workflow; stale is
an observed coordination state, not a test failure.

## Workflow

`.github/workflows/engineering-ops-drift.yml` is read-only:

- `pull_request` validates this tooling while it is a candidate;
- `workflow_dispatch` supports operator rechecks;
- hourly `schedule` becomes active only after a separately authorized merge.

Permissions are read-only (`contents`, `pull-requests`, `actions`). Checkout and
artifact upload actions are immutable-SHA pinned. The workflow writes a step
summary and uploads the two bounded reports. It does not edit PRs/issues,
dispatch other workflows, label/close work, or mutate repository settings.

## Current known drift that motivated this slice

At the repository reconstruction used to build this candidate:

- canonical main: `66d43f6fd51cf9cea08016dad335aaa04b711a24`;
- PR #238 actual HEAD: `6519b9f368a229da2b2787caf178f8ef956bda5b`, while its body declared
  `1e8005e68d41a8c45130693ebda28e1a57422256`;
- PR #319 still pinned #238 at `2aa33211...`.

Those facts are examples only, not hard-coded status truth. The live collector
must rediscover them (or their successors) from GitHub on every run.

## Authority boundary

Quality Engineering remains authoritative for test/evidence correctness;
Integration Lab remains authoritative for semantic combination; Golden remains
authoritative for customer acceptance; Assembly remains sole canonical
integration coordinator; War Room/CEO retain priority/control. This tooling
only moves and invalidates operational evidence metadata.
