# ObraSignal Resilience, Chaos & Failure Recovery

Status: **factory-owned cross-cutting contract / test-only / non-runtime / no production chaos / no automatic merge**

Canonical basis at creation: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`.
Permanent factory: #428.

## Mission

Own only the unowned discipline between a real or test-injected failure and a truthful, safe recovery result:

`FAILURE INJECTION -> DEGRADED MODE -> RECOVERY -> PARTIAL FAILURE TRUTH -> RETRY SAFETY -> RESILIENCE REGRESSION PREVENTION`.

This layer does not replace domain behavior. It creates reusable proof rules and deterministic test inputs, then routes any domain defect to its authoritative owner.

## Current owner map

| Failure boundary | Domain authority retained | Resilience responsibility |
|---|---|---|
| SQLite migration/corruption/backup/restore | Data Reliability #238 | deterministic injection shape; recovery-evidence completeness; cross-domain regression |
| source timeout/malformed/partial/stale | Source Health #327/#281 | partial/degraded truth; no false zero/complete result; recovery proof |
| Auth/JWKS/provider unavailable | Auth #289 + Operability #248 | retry/degraded classification; no false authentication result |
| RevenueCat unavailable/duplicate/out-of-order | Billing #83 | unsafe replay detection; convergence/recovery proof without becoming billing authority |
| push transport/receipt/retry | Notification Delivery #329/#263 | bounded retry/idempotency/retry-drain proof without becoming provider authority |
| customer incident/recovery communication | Support #355/#347 | provide failure/recovery evidence; Support retains severity/customer communication |
| production GO/NO-GO | Readiness #337 | resilience evidence is an input only; never self-promotes readiness |

Quality remains exact-head test authority; Integration Lab remains composition authority; Golden remains customer/system acceptance authority.

## Executable contract

`resilience_factory.py` is deliberately side-effect free and has no production registration.

### Service truth

Composed service state is one of:

- `HEALTHY`: every required and observed optional capability is healthy;
- `DEGRADED`: required capability remains usable but one known capability is degraded/unavailable;
- `UNAVAILABLE`: a required capability is unavailable;
- `UNKNOWN`: evidence is missing or unknown, so a stronger claim is not justified.

An empty evidence set is `UNKNOWN`, not healthy and not proof of an empty market/data set.

### Partial truth

Batch/partition outcomes preserve partiality:

- successes only -> `HEALTHY`;
- successes + known failures -> `DEGRADED`;
- failures only -> `UNAVAILABLE`;
- any unknown partition -> `UNKNOWN`;
- zero observations -> `UNKNOWN`.

This prevents a successful subset from being relabelled complete.

### Retry safety

Retries are allowed only when all of the following are true:

1. the failure class is explicitly retryable;
2. the maximum attempt count is not exhausted;
3. tenant safety and truth preservation remain intact;
4. if a mutation committed or its commit state is unknown, the owner has explicitly proven idempotency.

`UNKNOWN` is never retryable by default. A timeout after an uncertain write is not permission to replay the write. Successful replay does not prove the first attempt had no side effect.

The default contract caps attempts at three. Test backoff is deterministic and capped; runtime owners may add jitter while preserving the same maximum-attempt and unsafe-replay rules.

### Recovery truth

Recovery uses distinct states:

- `IN_PROGRESS`: service is still degraded/unavailable;
- `SERVICE_RESTORED`: service is healthy again, but end-to-end recovery evidence is incomplete;
- `RECOVERY_VERIFIED`: service healthy **and** expected state, tenant isolation, no silent data loss, retry quiescence and customer journey are all explicitly verified;
- `FAILED`: one of those explicit checks failed;
- `UNKNOWN`: service recovery state itself is unknown.

A 200 response or green CI run can establish neither `RECOVERY_VERIFIED` nor customer resolution by itself.

## Deterministic failure plans

`FailurePlan` names a bounded test point and exact attempts that should fail. It performs no monkey-patching, sleeping, network I/O, environment mutation or runtime registration. Domain tests may consume the plan through owner-local seams.

The machine-readable `resilience_manifest.json` inventories the first owner-routed scenarios and is audited fail-closed by the repository test suite.

## First failure matrix

1. DB unavailable -> required service unavailable; #238/#248 owner repair/recovery.
2. Partial migration or corruption -> fail closed; #238 owns storage behavior.
3. Source timeout -> degraded/unknown coverage, never empty-market success; #327/#281.
4. Source partial response -> partial truth stays degraded; #327/#281.
5. Source stale -> currentness is degraded/stale, never current by omission; #327/#281.
6. Auth provider unavailable -> unavailable, never invalid-credential fabrication; #289/#248.
7. Billing provider unavailable -> local paid-state mutation cannot be invented; #83.
8. Notification delivery failure -> application may remain usable but notification path is degraded; retry must be bounded/idempotent; #329/#263.

## Required regression pattern

Every confirmed resilience defect should produce:

1. exact failing scenario and owner;
2. deterministic failure plan or disposable-state reproduction where legitimate;
3. truthful service/partial state before repair;
4. explicit retry decision and mutation/idempotency evidence;
5. owner repair without weakening truth/tenant/data-safety contracts;
6. recovery proof including retry quiescence;
7. exact-head Quality regression;
8. Integration Lab composition when multiple owners interact;
9. Golden handoff when customer/device/system recovery is material.

## ACTIVE -> NEXT -> WAIT

**ACTIVE**
- keep #428 owner map current against repository truth;
- establish the executable non-runtime contract and exact-head tests;
- use owner-local failures to find the first concrete retry/degraded/recovery contradiction.

**NEXT**
- DB unavailable + partial migration/corruption matrix against #238;
- source timeout/malformed/partial/stale matrix against #327;
- Auth provider unavailable against #289/#248;
- Billing late/duplicate/out-of-order + provider-unavailable replay safety against #83;
- Notification retry exhaustion/receipt ordering against #329;
- composed partial-failure tests where unaffected customer capability must stay usable and truthful;
- resilience drift audit for owner contract movement;
- Integration Lab + Golden recovery handoffs.

**WAIT / EXTERNAL**
- destructive production chaos;
- production customer data/DB mutation;
- provider/secrets/config mutation;
- deploy/rollback execution;
- repository settings mutation;
- merge or queue/capability/source promotion.

`REPAIRABLE != BLOCKED`. `OTHER_OWNER != STOP`. `GREEN PR != RECOVERY VERIFIED`. `SERVICE_RESTORED != CUSTOMER VERIFIED`.
