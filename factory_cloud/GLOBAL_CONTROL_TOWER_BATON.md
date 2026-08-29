# GLOBAL CONTROL TOWER BATON

MISSION: one founder command routes every registered Factory without manual per-chat paths and preserves independent execution truth/BATON state.

BASE: `factory-cloud/app-development-control-plane` @ `3af6da227f63ecd17e076a13e1ebd5c11d12e9a5`
BRANCH: `factory-cloud/global-control-tower-routing`
PR: #722 (draft)

## DONE
- Deterministic internal route for every Factory from canonical registry identity/group.
- No per-Factory ChatGPT/chat URL is accepted or required by the router.
- ObraSignal parent/sub-Factory hierarchy is derived automatically.
- Global selection scopes: all, ObraSignal+subs, ObraSignal subs, business, development, single Factory.
- Generic portfolio worker boundary uses ONE global runtime, not one path per Factory.
- Factory identity and BATON travel in the execution payload; no shell interpolation.
- Unprovisioned portfolio runtime fails closed as WAIT, not false RUNNING.
- Persistent global dispatch batches + per-Factory item/result state in SQLite.
- Transport-neutral Control Tower API contract: POST `/v1/dispatch`, GET `/v1/batches/<id>`.
- Global dispatcher persists batch before execution and continues after local WAIT/BLOCKED/ERROR.
- Existing durable Factory Cloud app orchestrator is bridged into global control/app routes.
- One host runtime builder configures shared global state + shared app state + ONE shared portfolio worker.
- One-command CLI exists: `python -m factory_cloud.global_runtime <scope>`.
- Founder Control UI uses a single Control Tower endpoint and provides `LIGAR TODAS`, `OBRASIGNAL + SUBS`, `SUBS OBRASIGNAL`, `NEGÓCIOS`, `DESENVOLVIMENTO`.
- Switchboard source no longer depends on founder-entered per-Factory chat URLs for dispatch.
- Acceptance coverage exists for one-command multi-Factory dispatch and independent persisted results.
- Added deployable Control Tower container + persistent-host runbook.
- Portfolio worker can now be provisioned in either of two ONE-GLOBAL-runtime forms: one absolute executable OR one shared HTTPS endpoint. Both configured simultaneously fail closed as ambiguous.
- Remote worker HTTP is rejected; remote endpoint must be HTTPS. Embedded URL credentials are rejected. Optional bearer token is host-level, not per-Factory.
- Added endpoint-path tests preserving Factory identity/BATON payload and no per-Factory routes.

## EVIDENCE
- Earlier exact branch heads repeatedly passed Python + Mobile CI, including `24868e64d239773757e8b60960d5b8555f0049f0` (both SUCCESS).
- PR #722 remains open/draft and unmerged.
- New shared-endpoint implementation is on branch after that green head.
- Local clone/test attempt from the current execution container was impossible because outbound DNS to GitHub is unavailable; this is an environment limitation, not a test PASS or code failure.
- GitHub had not yet attached a workflow run to the new endpoint head when this BATON was written. Therefore the newest endpoint delta is `NOT_FULLY_VERIFIED` until exact-head CI runs.

## ACTIVE
Obtain exact-head CI for the newest shared-endpoint delta. In parallel, continue reducing the real runtime provisioning gap without reintroducing per-Factory manual paths.

## NEXT
1. Exact-head Python + Mobile CI GREEN for the newest branch head.
2. Provision one real non-ChatGPT-tab portfolio agent runtime as either the shared executable OR shared HTTPS endpoint.
3. Run real-runtime multi-Factory acceptance: one command → multiple independent Factory results/BATONs.
4. Verify one blocked Factory does not stop others against that real runtime.
5. Verify host restart/recovery and no false RUNNING.
6. Point deployed Founder Control Center at the real HTTPS Control Tower endpoint.
7. `LIGAR TODAS` → `scope=all`; `LIGAR OBRASIGNAL` → `scope=obrasignal`; no per-Factory paths entered by founder.

## WAIT / REAL EXTERNAL DEPENDENCY
A real autonomous portfolio agent runtime is not yet provisioned in the available connected environment. The architecture now accepts ONE shared executable or ONE shared HTTPS endpoint. No founder-entered path/URL per Factory is needed.

The current Vercel Switchboard project is suitable for the UI, but the Control Tower service requires durable execution state and a real agent runtime. Do not claim the existing static Vercel project alone supplies that runtime.

## SAFETY
No merge, customer-data mutation, billing, secrets rotation, provider mutation or cross-Factory production authority is authorized by this branch. Execution remains fail-closed when a required runtime is unavailable.

## RESUME_AT
Exact-head CI → provision one shared portfolio agent runtime → real multi-Factory acceptance → deployed Founder Control Center single-endpoint wiring.
