# GLOBAL CONTROL TOWER BATON

MISSION: one founder command dispatches every eligible Factory through automatically derived internal routes; no founder-entered per-Factory chat URL/path.

BASE: `factory-cloud/app-development-control-plane` current-base successor
BRANCH: `factory-cloud/global-control-tower-routing-v2`
PR: #777 (draft)

## DONE
- Rebuilt directly on latest Factory Cloud base after PR #722 diverged/conflicted.
- PR #777 is mergeable on the current base; no stale control-plane files were overwritten.
- deterministic route for every Factory from canonical registry identity/group.
- ObraSignal parent/sub-Factory hierarchy and global scopes: all / OS+subs / OS subs / business / development / single Factory.
- no manual ChatGPT/conversation URL accepted or required.
- persistent SQLite global batches and independent per-Factory execution/result truth.
- WAIT/BLOCKED/ERROR on one route does not stop other routes from being attempted.
- bridge from global routes to existing durable Factory Cloud application orchestrator.
- one portfolio runtime boundary: one absolute executable OR one shared endpoint, never one path per Factory.
- remote portfolio worker requires HTTPS and one host-level bearer token.
- worker result identity and status are validated fail-closed; worker cannot spoof Factory/route or claim unsupported RUNNING.
- Control Tower HTTP API supports bearer authentication and exact-origin CORS allowlist.
- health endpoint remains separate from execution API.
- one-command Founder client and dedicated Control Tower UI source added.
- deployable container, persistent-host runbook and systemd unit added.
- tests cover routing, persistent state, blocked-route continuation, worker security, API auth/origin and restart persistence.

## EVIDENCE
- PR #777 is OPEN / DRAFT / MERGEABLE on base `factory-cloud/app-development-control-plane`.
- current v2 branch head before this BATON: `41d9f4262d482cb3d534f6833e3e6cc33261aa9e`.
- exact-head ObraSignal Quality run #3436 was IN_PROGRESS when last checked; newest BATON commit requires fresh exact-head CI.
- external autonomous portfolio-agent runtime is still NOT_PROVISIONED in connected tooling; do not claim business Factories are executing yet.

## ACTIVE
Obtain exact-head CI GREEN on PR #777 while continuing all safe host/runtime/UI readiness work that does not require the missing external agent host.

## NEXT
1. exact-head Python + Mobile SUCCESS for final v2 head.
2. provision one persistent non-ChatGPT-tab portfolio agent runtime via shared executable or HTTPS endpoint.
3. real acceptance: one command -> multiple independent Factory results/BATONs.
4. real blocked-Factory continuation test.
5. real process restart/recovery test.
6. expose Control Tower through HTTPS with authentication.
7. connect Founder Control Center to one same-origin/proxied Control Tower endpoint.
8. verify `LIGAR TODAS` and `OBRASIGNAL + SUBS` end-to-end without manual routes.

## WAIT / EXTERNAL
No connected persistent compute/provider currently available here can provision the real long-lived portfolio agent runtime. Vercel static UI alone is not that runtime, and durable SQLite must not be falsely treated as persistent serverless storage.

## SAFETY
No automatic merge, production deployment, customer data, billing, secrets rotation, provider mutation or cross-company production authority.

## RESUME_AT
Exact-head CI -> persistent agent host provisioning when an eligible host becomes available -> real multi-Factory acceptance -> Founder Control Center live endpoint wiring.
