# ObraSignal Customer Support, Incident & Service Operations

Status: **support-owned contract / non-runtime / no production mutation / no automatic merge**

Canonical reconstruction basis at creation: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`.

This document owns the support and incident-response layer only. Runtime service health, authentication, billing authority, source freshness, storage recovery, production readiness and Golden acceptance remain with their existing owners. A green branch or CI run is not customer recovery evidence.

## Truth rules

- `UNKNOWN` is not success, zero, absence, healthy or retryable.
- A customer workaround is not a product fix.
- Service restored is not root cause closed.
- Green CI is not incident resolution.
- Candidate evidence is not canonical/deployed evidence.
- No customer-facing resolution claim exists until recovery is verified on the relevant surface.
- Support evidence must not require unrelated customer data or a cross-tenant selector.

## Customer failure contract

The support-facing semantic vocabulary is deliberately small:

| Class | Meaning | Must not imply |
|---|---|---|
| `RETRYABLE` | the owning contract explicitly proves a safe retry path | that every retry will succeed |
| `UNAVAILABLE` | required service/dependency is unavailable | empty/zero result or customer fault |
| `DEGRADED` | service is operating with material reduced capability | healthy/full coverage |
| `STALE` | available data is older than its owning freshness contract permits | current market truth |
| `UNKNOWN` | evidence is insufficient to classify more precisely | zero, healthy, failure cause or retryability |
| `AUTH_REQUIRED` | valid authenticated context is required | provider outage or permission denial |
| `PERMISSION_DENIED` | identity exists but operation is not permitted | missing record |
| `NOT_FOUND` | requested resource is not visible in the authorized scope | existence in another tenant |
| `CONFLICT` | authoritative/current evidence conflicts | automatic winner or silent overwrite |
| `INVALID_INPUT` | request validation is known to have failed | conflict, retryability, dependency failure or unknown root cause |

`INVALID_INPUT` was added after reconstructing canonical profile/workflow validation behavior. Known validation failure cannot truthfully be collapsed into `CONFLICT` or `UNKNOWN` simply to preserve the initial vocabulary.

Transport-specific HTTP mapping remains with the API/domain owner. Support must not manufacture a status mapping merely to make errors look uniform.

## Incident severity

Severity is based on **observed impact**, not branch labels or guesses:

- `SEV0`: confirmed tenant leakage, confirmed data loss, or confirmed security compromise.
- `SEV1`: billing/access outage or critical customer-journey outage.
- `SEV2`: source/service degradation with bounded customer impact and no SEV0/1 evidence.
- `SEV3`: isolated single-customer defect with no higher impact evidence.

No observed impact means **unclassified**, not silently `SEV3`.

## Safe support evidence pack

The repository contract permits only bounded operational metadata:

- opaque correlation identifier;
- timezone-aware observation timestamp;
- service area;
- customer failure class;
- service readiness state;
- recovery state;
- bounded build/version identifier;
- bounded dependency state;
- allowlisted scalar diagnostic fields such as HTTP status, operation, bounded error code, component, retry-after, attempt and state version.

It intentionally has no raw profile/workflow/customer payload, arbitrary headers, free-form dump, client-selected tenant scope or unrelated customer data. String diagnostics are token-like rather than free-form, and numeric diagnostics are explicitly ranged. A specialist may keep additional private evidence under its own access controls, but it must not be copied into this support pack by default.

## Supportability matrix

This matrix is a routing/diagnostic overlay. It does not replace specialist health/readiness contracts.

| Journey | Typical symptom classes | Safe evidence | Primary owner / evidence source | Customer-safe recovery principle |
|---|---|---|---|---|
| Signup / login | `AUTH_REQUIRED`, `UNAVAILABLE`, `PERMISSION_DENIED`, `UNKNOWN` | correlation id, build, bounded Auth health state | Production Auth / #289 | relogin only when session/auth evidence supports it; provider outage is not fixed by repeated login |
| Profile | `INVALID_INPUT`, `RETRYABLE`, `UNAVAILABLE`, `CONFLICT`, `UNKNOWN` | bounded validation code, profile write/read outcome, Radar recalculation state, correlation id | profile/API; #341 and #360 | re-read durable profile before asking customer to re-enter data; invalid input stays a validation result; refresh/recalculate idempotently |
| Radar | `STALE`, `DEGRADED`, `UNAVAILABLE`, `UNKNOWN` | source coverage/freshness, stats state, build | Source Health #327/#281 + Web/Mobile consumers | refresh only through public contract; stale/empty must not become zero-market |
| Sources | `STALE`, `DEGRADED`, `UNAVAILABLE`, `UNKNOWN` | per-source health/freshness/cursor metadata from owner contract | Source Health #327 | retain historical opportunities; do not tell customer the market is empty from a failed source |
| Opportunity / detail | `NOT_FOUND`, `STALE`, `CONFLICT`, `UNKNOWN` | authorized resource lookup, lifecycle/source state, build | Opportunity/Web/Source owners | refresh current opportunity truth; do not reveal whether another tenant can see a resource |
| Evidence | `UNAVAILABLE`, `STALE`, `CONFLICT`, `UNKNOWN` | bounded customer Evidence status/provenance only | Q080 Evidence owner / Golden | hide/unavailable is preferable to fabricated explanation; never expose private graph/profile state |
| Workflow | `INVALID_INPUT`, `RETRYABLE`, `NOT_FOUND`, `CONFLICT`, `UNKNOWN` | bounded validation code, authorized read-before/write/readback, state version where available | workflow/API/Auth E2E; #360 | invalid status is not a conflict; re-read before retry; preserve prior state on failed mutation; no direct production DB repair |
| Notifications | `PERMISSION_DENIED`, `UNAVAILABLE`, `DEGRADED`, `UNKNOWN` | permission state, registration state, bounded delivery/tap state | #259, #263/#329 | permission recovery and remote-delivery recovery are distinct; re-register only through owned path |
| Evaluation | `UNKNOWN`, `CONFLICT`, `UNAVAILABLE` | real activation events + server lifecycle state | #287/#333 + lifecycle owner | retries/restarts must not reset activation; absence of billing proof must not invent Evaluation |
| Billing | `UNAVAILABLE`, `CONFLICT`, `UNKNOWN`, `PERMISSION_DENIED` | server-authoritative billing state + bounded provider status | #83/#288 | recheck authoritative provider/server projection; client entitlement cannot unlock Pro |
| Account / privacy | `CONFLICT`, `UNAVAILABLE`, `UNKNOWN`, `PERMISSION_DENIED` | authenticated lifecycle state + bounded deletion/export status | #292/#342 + Auth/Billing/Mobile handoffs | no destructive cleanup by guess; pending external revocation remains pending |

## Support-facing incident overlays

These are **triage and escalation overlays**, not replacement specialist runbooks.

### Auth outage
1. Detect: 401/503 pattern plus bounded Auth health/build evidence.
2. Contain: stop advice that creates login loops or identity churn.
3. Diagnose: distinguish `AUTH_REQUIRED` from provider `UNAVAILABLE` using Auth-owned diagnostics.
4. Route: Production Auth owner; Security if compromise evidence exists.
5. Recover: use Auth-owned session/provider recovery path only.
6. Verify: authenticated identity + required private journey on the exact deployed build.
7. Close root cause only after the owner has a regression/operational prevention action.

### Database degradation / migration failure / data corruption
1. Detect from application symptoms plus Data Reliability-owned evidence.
2. Contain writes only when an authorized operational owner determines that is required; support does not mutate production.
3. Route to #238/Data Reliability.
4. Never ask a customer to delete local/server data as a generic fix.
5. Recovery/restore/cutover follows the Data Reliability contract and authorization boundary.
6. Verify tenant isolation and the affected customer journey after recovery.

### Source outage / stale Radar / external dependency outage
1. Use source-specific freshness/health, never aggregate emptiness as proof of market absence.
2. Preserve historical opportunities and disclose stale/degraded/unknown state truthfully.
3. Route source defect to #327/#281 or the relevant source owner.
4. Verify source health and customer Radar independently; a source becoming reachable is not by itself customer recovery.

### Billing verification failure
1. Preserve `UNKNOWN/UNAVAILABLE` when authoritative billing cannot be verified.
2. Never grant Pro from local/client state and never convert provider failure into Evaluation.
3. Route authority/security failures to #83/#288.
4. Verify server-authoritative entitlement after recovery before stating access is restored.

### Notification failure
1. Split permission, registration, remote provider delivery and tap-return into separate evidence states.
2. A foreground/local notification is not proof of closed-app remote delivery.
3. Route to #259 or #263/#329 as appropriate.
4. Verify the intended current opportunity after tap; unavailable targets return truthfully to current Radar.

### Bad deployment
1. Identify the exact deployed build before diagnosis.
2. Containment/rollback remains Release/Deployment ownership and requires its authorization contract.
3. Support preserves customer impact/correlation evidence and does not mutate production.
4. After rollback, verify the customer journey; do not close root cause merely because the previous build is restored.

### Cross-tenant suspicion
1. Treat as immediate high-risk escalation; do not browse unrelated accounts to investigate.
2. Preserve the reporting customer's bounded evidence and exact build/time.
3. Route to Security + relevant tenant-state owner.
4. Any confirmed tenant leakage is `SEV0`.
5. Recovery requires tenant-isolation verification and regression acceptance, not only cache/session reset.

## Current known-issue handoffs at creation

These are repository findings, not live-production incident declarations:

- #360: canonical profile/workflow validation does not yet expose one bounded support-safe `INVALID_INPUT` envelope; workflow currently derives a `ValueError` message from request input. Support owns the class; API/domain owners own route adoption.
- #341: profile may persist before synchronous Radar bootstrap fails; support recovery must re-read durable profile before asking for another write.
- #281/#327: source-specific freshness/coverage contract exists as a candidate; stale/partial data must not become market absence.
- #288/#83: billing verification failure must not become Evaluation or client-authoritative access.
- #291/#322: Mobile cross-account private-cache risk has a green candidate but still requires physical-device acceptance.
- #263/#329: remote background/closed-app notification delivery and tap-return require physical/config evidence.
- #292/#342: account deletion/export has an implementation candidate but overall deletion remains pending external-owner proof.
- #238: storage recovery/backup/restore remains the Data Reliability authority.
- #248: security/operability runbook and diagnostic redaction remain the Operability/Security authority.
- #337: release/customer readiness remains the GO/NO-GO authority, not this support layer.

## Incident to regression contract

For every confirmed product defect, preserve:

1. exact symptom and customer-visible failure class;
2. reproduction that does not require unrelated customer data;
3. owner and ownership boundary;
4. exact affected build/version when known;
5. safe workaround, if one exists, explicitly labelled workaround;
6. repair acceptance condition;
7. regression test where technically legitimate;
8. Golden handoff for customer/system acceptance when journey material;
9. release/deployment status separately from code-fix status;
10. customer confirmation/verified recovery separately from root-cause closure.

## Observability handoff

Current-main repository search did not find a cross-cutting request/correlation-id contract. Runtime/API propagation and structured logging belong to Operability/API owners; this support module defines only the bounded identifier/evidence shape it will consume. The desired handoff is:

`request -> opaque correlation id -> response-safe reference -> privacy-safe structured operational log -> support evidence pack`

No account identifier, customer payload or authorization material is required in the support-facing response.

## Failure injection backlog

Test-only and owner-approved scenarios, never production chaos by this cell:

- dependency unavailable;
- timeout;
- partial response;
- malformed/corrupt persisted state through disposable storage;
- expired/missing authentication;
- billing provider unavailable;
- source stale/unavailable;
- notification delivery failure.

Each injection must prove truthful failure class, safe evidence, no cross-tenant exposure, recoverability, and no false success.

## Customer communication truth

Communication templates may say that service is degraded, unavailable, delayed, under investigation, restored, or verified only when the corresponding evidence exists. “Resolved” is not used as a synonym for “HTTP requests are succeeding again.” Billing access, data currency, tenant safety and recovery each require their own verification where relevant.

## ACTIVE / NEXT / WAIT

**ACTIVE:** bounded support semantics + safe evidence + owner routing + supportability/runbook overlays + validation gap #360.

**NEXT:** public error-contract integration through owner-safe seams; correlation-id operability handoff; failure injection; incident-to-regression automation; living known-issue ledger; evidence-supported service objectives.

**WAIT / OTHER OWNER:** #248 Security/Operability, #238 recovery, #327 source freshness, Auth, #83 Billing, #322 Mobile session, #329 notifications, #342 privacy, #337 readiness, Golden acceptance. Other-owner work never stops independent support work.
