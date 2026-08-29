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
- Generic portfolio worker boundary uses ONE globally configured executable, not one path per Factory.
- Factory identity and BATON travel over JSON stdin; no shell interpolation.
- Unprovisioned portfolio runtime fails closed as WAIT, not false RUNNING.
- Persistent global dispatch batches + per-Factory item/result state in SQLite.
- Transport-neutral Control Tower API contract: POST `/v1/dispatch`, GET `/v1/batches/<id>`.
- Global dispatcher persists batch before execution and continues after local WAIT/BLOCKED/ERROR.
- Existing durable Factory Cloud app orchestrator is bridged into global control/app routes.
- One host runtime builder configures shared global state, shared app state and ONE portfolio-worker executable only.
- One-command CLI exists: `python -m factory_cloud.global_runtime <scope>`.
- Founder Control JS client uses one Control Tower endpoint and exposes `ligarTodas`, `ligarObraSignal`, `ligarSubsObraSignal`, `ligarNegocios`, `ligarDesenvolvimento`.
- Acceptance test uses one real temporary executable to dispatch every business Factory and verifies persisted DONE results without any per-Factory path.

## EVIDENCE
- Previous exact heads repeatedly passed Python + Mobile CI through `1b978ec9d608146947843cdac1f4b5ccbae302be`.
- Current implementation commits include persistent dispatch, API boundary, app-orchestrator bridge, one-host runtime, Founder client, and shared-worker acceptance coverage.
- Exact-head CI must be SUCCESS on the final branch head before this slice is classified GREEN.

## ACTIVE
Validate exact current HEAD. If GREEN, proceed to provision/wire the real shared portfolio agent runtime and connect the deployed Founder Control Center UI to the single Control Tower endpoint.

## NEXT
1. Exact-head Python + Mobile CI GREEN.
2. Provision one real non-ChatGPT-tab portfolio agent runtime executable/endpoint.
3. Run real-runtime multi-Factory acceptance: one command → multiple independent Factory results/BATONs.
4. Verify one blocked Factory does not stop others against that real runtime.
5. Verify host restart/recovery and no false RUNNING.
6. Replace deployed Switchboard local chat URL/copy behavior with the single Control Tower API client.
7. `LIGAR TODAS` → `scope=all`; `LIGAR OBRASIGNAL` → `scope=obrasignal`; no per-Factory paths entered by founder.

## WAIT / REAL EXTERNAL DEPENDENCY
A real autonomous portfolio agent runtime is not yet provisioned in the available execution environment. The architecture now needs only ONE shared worker runtime path/endpoint; it does not need founder-entered paths for each Factory.

## SAFETY
No merge, production deployment, customer data, billing, secrets, provider mutation or cross-Factory production authority is authorized by this branch. Execution remains fail-closed when a required runtime is unavailable.

## RESUME_AT
Exact-head CI → real shared portfolio agent runtime provisioning → real multi-Factory acceptance → deployed Founder Control Center single-endpoint wiring.
