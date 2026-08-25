# ObraSignal — Security & Operability Runbook

Status: repository operational contract. No destructive action is authorized by this document.

## State semantics

- **HEALTHY** — the observed contract is satisfied with current evidence.
- **DEGRADED** — service remains usable but a measured dependency, freshness, latency or error boundary is outside its normal observed range.
- **CRITICAL** — a customer-truth, tenant-isolation, authentication, persistence, deployment or availability boundary is failing and continued operation can cause material harm.
- **UNKNOWN** — evidence is missing, stale or insufficient. UNKNOWN must never be reported as HEALTHY.

## SLI/SLO rules

Do not invent availability percentages without a retained observation window. Until a trustworthy baseline exists, publish observed counts/timestamps and state classification only.

Truthful SLIs currently available or derivable from repository/runtime evidence:

- exact deployed build SHA from `/api/v1/health` / `X-ObraSignal-Build`;
- API reachability and HTTP status from production smoke;
- authenticated-boundary status from owned Auth health (handoff only);
- stage latency from retained latency metrics;
- source freshness / last successful observation where source health exposes it;
- last completed sync timestamp;
- DB contention test evidence;
- workflow run status for exact-head Quality / production smoke.

Latency classification keeps the repository's existing relative-baseline contract: recent/baseline ratio >=2 is DEGRADED and >=4 is CRITICAL only when both windows have real samples. No samples => UNKNOWN.

## Alerting thresholds that are defensible now

- exact production build differs from the expected release SHA after the deployment grace window: CRITICAL release incident;
- protected API unexpectedly returns success without authentication: CRITICAL security incident;
- tenant-isolation assertion failure: CRITICAL, contain writes and customer-facing access to the affected surface;
- source has explicit freshness SLA/expected cadence and exceeds that observed bound: DEGRADED, then CRITICAL only when the source owner contract defines a critical boundary;
- latency ratio >=2 with valid baseline: DEGRADED; >=4: CRITICAL;
- no baseline / missing telemetry: UNKNOWN, not HEALTHY.

## API unavailable

**DETECT** — production smoke/health fails or sustained 5xx is observed.

**CONTAIN** — stop nonessential write automation; do not mutate data or secrets. Preserve evidence and exact build SHA.

**DIAGNOSE** — verify DNS/TLS, Render service state, exact deployed SHA, process start, DB reachability and recent workflow/deploy history.

**ROLLBACK** — revert only the last independently identified bad deployment under explicit deployment authority.

**RECOVER** — restore a previously validated build/configuration.

**VERIFY** — health, protected boundary, customer read path, exact build SHA and Quality evidence.

**POST-INCIDENT EVIDENCE** — timestamps, affected endpoints, build SHAs, root cause, rollback/recovery evidence and missing telemetry.

## Auth provider failure — Production Auth owner handoff

**DETECT** — provider health is degraded/misconfigured or authenticated E2E fails.

**CONTAIN** — fail closed; never bypass authentication.

**DIAGNOSE** — hand off provider/JWKS/config investigation to Production Auth owner with bounded diagnostics only.

**ROLLBACK / RECOVER** — Auth owner only; no secret rotation by this runbook.

**VERIFY** — unauthenticated rejection plus authenticated E2E on exact deployed build.

**POST-INCIDENT EVIDENCE** — secret-free provider category, timestamps and exact SHA.

## Source outage / stale source — source owner handoff

**DETECT** — failed fetches, stale last-observed timestamps, ingest lag or source-health degradation.

**CONTAIN** — mark truth as stale/unknown where supported; do not fabricate freshness or silently substitute unrelated sources.

**DIAGNOSE** — distinguish provider outage, rights/access change, parser failure and internal scheduler/worker failure.

**ROLLBACK** — revert only the source-owned change that introduced the failure.

**RECOVER** — resume from the source owner's safe cursor/checkpoint contract.

**VERIFY** — fresh lawful observations, no duplication, lineage intact.

**POST-INCIDENT EVIDENCE** — outage window, affected source, last-good observation, recovery cursor and owner.

## DB corruption / failed migration — Data Reliability owner handoff

**DETECT** — integrity checks, startup failures, impossible constraints or persisted-state inconsistency.

**CONTAIN** — stop unsafe writes; preserve the database and logs. No destructive repair.

**DIAGNOSE / ROLLBACK / RECOVER** — Data Reliability owner only, using its backup/migration/recovery contract.

**VERIFY** — integrity, tenant isolation and application read/write contracts.

**POST-INCIDENT EVIDENCE** — exact schema/build, checks performed and recovery evidence.

## Billing provider failure — Billing #83 handoff

**DETECT** — billing status/provider errors outside the webhook implementation owned by #83.

**CONTAIN** — do not grant paid capability from uncertain billing evidence and do not duplicate webhook logic.

**DIAGNOSE / ROLLBACK / RECOVER** — Billing owner.

**VERIFY** — bounded billing-status contract and owner tests.

**POST-INCIDENT EVIDENCE** — provider category, affected window and owner handoff.

## Bad deployment

**DETECT** — expected SHA differs from served SHA, startup regression, smoke failure or exact-head contract failure.

**CONTAIN** — stop further deployment mutation and preserve the failing SHA.

**DIAGNOSE** — compare intended release commit, Render-served build, workflow run and prior validated build.

**ROLLBACK** — deploy/revert to the immediately prior validated build under explicit deployment authority.

**RECOVER** — repair on a noncanonical branch, exact-head Quality, then normal release path.

**VERIFY** — served SHA, smoke, auth boundary and customer-critical read path.

**POST-INCIDENT EVIDENCE** — bad/good SHAs and exact workflow runs.

## Tenant-isolation incident

**DETECT** — any cross-account read/write, IDOR, account_id mismatch or tenant regression failure.

**CONTAIN** — classify CRITICAL; stop the affected write/read surface where operationally possible without destructive mutation. Preserve evidence. Do not notify through insecure channels containing customer data.

**DIAGNOSE** — identify endpoint, identity derivation, account-scoping predicate and affected object class. Do not inspect more tenant-private data than necessary.

**ROLLBACK** — revert the introducing code/config only when identified.

**RECOVER** — restore server-derived tenant scope and add a reproducing regression.

**VERIFY** — adversarial two-tenant tests on all affected operations.

**POST-INCIDENT EVIDENCE** — minimum necessary IDs, timestamps, code SHA and containment/recovery actions; no notes/profile contents in the incident record.

## Credential exposure

**DETECT** — token/key/credential appears in logs, commits, artifacts, errors or public output.

**CONTAIN** — remove public exposure where possible and stop further propagation. Do not paste the credential into tickets/chat.

**DIAGNOSE** — determine credential class, scope and exposure window without reproducing the secret.

**ROLLBACK** — revert the leaking code/logging path.

**RECOVER** — credential rotation/revocation belongs to the credential owner and requires explicit authority.

**VERIFY** — secret-free logs/errors and revoked old credential where applicable.

**POST-INCIDENT EVIDENCE** — credential type, fingerprint/identifier only if safe, exposure window and rotation owner.

## Degraded latency

**DETECT** — valid recent/baseline ratio >=2.

**CONTAIN** — avoid retry amplification and additional expensive background work.

**DIAGNOSE** — identify stage, DB contention, source latency, query volume and recent deployment changes.

**ROLLBACK** — only a confirmed introducing change.

**RECOVER** — restore bounded queries/timeouts or dependency health.

**VERIFY** — new observed samples return below the degradation boundary; do not declare recovered from one synthetic request.

**POST-INCIDENT EVIDENCE** — recent/baseline sample counts and ratios.

## Privacy-safe incident evidence

Aligned with `PRIVACY_NON_INTRUSION_PRINCIPLE.md`: operational evidence must minimize company-private data. Never record bearer tokens/JWTs, provider credentials, webhook secrets, profile payloads, notes, commercial decisions or confidential company state in incident prose. Prefer account/object opaque identifiers, counts, bounded error categories, timestamps and commit SHAs.

## Repository protection recommendation (settings mutation requires founder authorization)

For `main`:

1. require pull requests before merging;
2. require `ObraSignal Quality` exact-head check and any separately owned release/security check only after that check is stable;
3. require branch to be up to date before merge when GitHub can do so without creating stale merge-queue behavior;
4. block force pushes and branch deletion;
5. require conversation resolution;
6. apply rules to repository administrators/founder as well, with an emergency bypass limited to the founder and used only for documented incidents;
7. disallow direct pushes to `main`; all normal changes enter through PR;
8. preserve linear-history preference only if it does not conflict with the repository's intentional merge-commit evidence model; current ObraSignal uses explicit merge commits, so do **not** mandate linear history now.

No repository setting is changed by this branch.

## Distributed abuse control recommendation

Do not use per-process in-memory rate limiting as a production control. Configure a shared/edge limiter before claiming RATE-LIMITED. Initial safe policy to validate with real traffic:

- health/static read probes: generous burst, monitor first;
- authenticated ordinary reads: per-account + per-IP shared bucket;
- expensive profile recalculation writes: materially lower per-account burst;
- workflow writes: moderate per-account burst;
- malformed/unauthenticated abuse: per-IP bucket with predictable 429 and `Retry-After`;
- never key tenant limits from client-supplied account IDs.

Exact numeric production limits remain UNKNOWN until real customer traffic establishes a baseline.
