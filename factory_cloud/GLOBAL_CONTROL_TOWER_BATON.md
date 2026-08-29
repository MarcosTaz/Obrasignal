# GLOBAL CONTROL TOWER BATON

MISSION: one founder command routes every registered Factory without manual per-chat paths.

BASE: `factory-cloud/app-development-control-plane` @ `3af6da227f63ecd17e076a13e1ebd5c11d12e9a5`
BRANCH: `factory-cloud/global-control-tower-routing`
PR: #722 (draft)

## DONE
- Deterministic internal route for every Factory from canonical registry identity/group.
- No per-Factory ChatGPT/chat URL is accepted or required by the router.
- ObraSignal parent/sub-Factory hierarchy is derived automatically.
- Global selection scopes: all, ObraSignal+subs, ObraSignal subs, business, development, single Factory.
- Generic portfolio worker boundary uses one globally configured executable, not one path per Factory.
- Factory identity and BATON travel over JSON stdin; no shell interpolation.
- Unprovisioned portfolio runtime fails closed as WAIT, not false RUNNING.
- Unit tests added for route uniqueness, OS grouping, no manual paths and worker boundary.

## EVIDENCE
- PR #722 exact head before this BATON: `000108b6f0c4adc13f3ffc67ef4ff8362cda7854`.
- Python CI on that exact head: SUCCESS.
- Mobile CI was still in progress when this BATON was written; new commit requires fresh exact-head CI.

## ACTIVE
Provision/wire the real shared portfolio Factory agent runtime and connect the Founder Control Center `LIGAR TODAS` action to Global Control Tower dispatch.

## NEXT
1. Add persistent dispatch-batch state and per-Factory execution/result state.
2. Add a Control Tower service/API for `all`, `obrasignal`, `obrasignal-subs`, `business`, `development`.
3. Wire Factory Cloud application routes to existing durable app orchestrator.
4. Wire portfolio routes to one persistent agent/worker runtime.
5. Change Switchboard UI from local chat URL storage/copy to Control Tower API dispatch.
6. Verify one command → multiple Factory dispatches → independent results/BATONs.
7. Verify one blocked Factory does not stop others.
8. Verify restart/recovery and no false RUNNING.

## WAIT / REAL EXTERNAL DEPENDENCY
A real non-ChatGPT-tab portfolio agent runtime still needs to be provisioned. The code now requires only one shared worker runtime path/endpoint rather than manual paths for every Factory.

## SAFETY
No merge, production deployment, customer data, billing, secrets, provider mutation or cross-Factory production authority is authorized by this branch.

## RESUME_AT
Implement persistent dispatch-batch state + HTTP/service boundary, then provision the shared portfolio worker runtime and run multi-Factory acceptance tests.
