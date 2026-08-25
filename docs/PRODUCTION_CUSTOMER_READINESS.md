# Production & Customer Readiness Factory

Status: **EVIDENCE / READINESS ORCHESTRATION ONLY — NOT MERGE OR DEPLOY AUTHORIZATION**

This factory answers one narrow question: what still separates the exact canonical product from a product that can truthfully be called deployable, customer-usable, operable, recoverable and supportable?

It does not take implementation ownership already assigned to Auth, Billing, Evaluation, Mobile, Notifications, Source Health, Data Reliability, Golden, Integration Lab, Assembly or another specialist. It never owns production configuration, secrets, repository settings, Master Queue/capability/source promotion, merge or deploy authority.

## Truth hierarchy

`GREEN CODE != INTEGRATED SYSTEM != DEPLOYED PRODUCT != REAL CUSTOMER PROOF != SUPPORTABLE SAAS`

The executable release snapshot is `production_readiness_manifest.json`, validated by `production_readiness.py`. The snapshot is stale as soon as canonical `main` moves; `--current-main-sha` rejects drift instead of transferring historical green evidence.

Canonical snapshot basis: `66d43f6fd51cf9cea08016dad335aaa04b711a24`.

Release targets:

- `CURRENT_WEB_SAAS` — Web customer release; Mobile/remote push remain visible but are not prerequisites.
- `FULL_MULTI_CHANNEL` — includes Mobile and Notifications as blocking gates.

`UNKNOWN` fails closed. A candidate PR, prebuild, mergeable tree, Quality/CodeQL green or Golden result on a noncanonical tree cannot become production release proof through this contract.

## Current first-order truth

- **AUTH — PASS (bounded):** current-main Production Smoke + Authenticated E2E prove the current provider-mode Auth scope.
- **TENANT — UNKNOWN:** #335 current HEAD `91d3fd53` now supplies an isolated test-only tenant-safe fixture seam and is Quality+CodeQL green, but it is noncanonical; #289 still needs the nested workflow-response parser repair and FULL no-skip consumption; #68 real-browser A/B proof remains open. Mobile A→B remains physical Golden when Mobile is in target scope.
- **WEB — NO_GO:** #68 still needs the real production-configured browser journey. `web_production_browser_preflight.json` + `web_production_browser_preflight.py` now make the config, journey, evidence and GO/NO-GO rules executable. Saved/watch is explicitly nonblocking unless canonical product scope changes; current Web billing may remain informational but must be truthful.
- **BILLING — NO_GO:** #83 current HEAD `3c00cff4` remains RED with Billing Security failure and Quality `18 failed / 720 passed / 2 skipped`.
- **EVALUATION — NO_GO:** #333 `f6d4e8a0` is green candidate evidence but noncanonical and still depends on repaired Billing + Golden lifecycle composition.
- **PRIVACY — NO_GO:** #292 still lacks/proves neither provider recovery, tenant-safe export nor account deletion postconditions.
- **SECURITY — NO_GO:** GitHub `main` remains unprotected with no required checks/rulesets. Applying branch protection is a founder/settings authorization boundary. #248 is green candidate hardening, not canonical proof.
- **SOURCES — UNKNOWN:** #327 `be8bda85` and #331 `ba339435` provide green source-health contract/integration preproof; #281 remains open until canonical integration + independent Golden customer acceptance.
- **DATA/RECOVERY — UNKNOWN/NO_GO:** #238/#319 provide strong candidate mechanics but not canonical/off-disk/provider recovery proof.
- **GOLDEN/CUSTOMER_PROOF — NO_GO:** the minimum sellable customer spine is not yet accepted on one exact canonical deployed release.

## Executable operability acceptance

`operability_acceptance.py` + `operability_acceptance_observation.json` encode the anti-false-ready rule that liveness is not readiness.

Current main can return `ok=true` while DB, worker and aggregate critical dependencies remain unproven. The worker catches sync exceptions, prints them and continues sleeping without a canonical heartbeat/stalled/degraded readiness state.

The acceptance contract fails closed for:

- DB `DEGRADED / UNAVAILABLE / UNKNOWN`;
- worker `DEGRADED / STALLED / UNAVAILABLE / UNKNOWN`;
- critical dependency `DEGRADED / UNAVAILABLE / UNKNOWN`;
- support correlation `UNSAFE / UNKNOWN`;
- canonical-main drift.

A support correlation identifier can be `READY` only if it is opaque and explicitly excludes bearer/JWT/secrets, private profile/note payloads and raw account identifiers. Even full operability `READY` prints `release_go=no`.

Exact runtime implementation gaps were routed to Security/Operability #248 in comment `5415723385`; #337 does not duplicate #248 implementation.

## #68 production-browser preflight

`web_production_browser_preflight.py` + `web_production_browser_preflight.json` require all blocking observations on the same exact deployed canonical build.

Configuration proof covers production Web origin, public Supabase build inputs without recording values, production API origin, Supabase redirect behavior, backend provider Auth, exact CORS origin, deterministic tenant-safe customer data and isolated A/B principals.

Browser journey proof covers signup/login, hard reload/session restore, onboarding/profile save, first truthful Radar, deterministic detail/source, workflow persistence, A/B isolation, logout/relogin/return, degraded/offline/partial states, responsive/accessibility and truthful informational Web billing.

Any required `FAIL`, `UNKNOWN`, `BLOCKED_EXTERNAL`, conditional skip, build mismatch, tenant leak, secret/private evidence capture or false empty/degraded state => #68 `NO_GO`.

## First-value measurement — measure before optimize

The current customer path is synchronous:

`POST /api/v1/profile -> save_profile -> bootstrap_account -> immediate GET /api/v1/radar`

A disposable-SQLite benchmark on readiness HEAD `1007f984`, 20 iterations per case, preserved account scope, classified every seeded row, matched persisted decision count and required the first Radar to contain no `SEM DECISÃO` benchmark rows.

Observed on that runner:

- synthetic 25 rows: first-value p50/p95 ≈ **245 / 514 ms**;
- bounded 250 rows (`MAX_BOOTSTRAP_ROWS`): p50/p95 ≈ **2342 / 4375 ms**;
- Radar GET was ~2–4 ms and `save_profile` ~3 ms p50, localizing latency to synchronous bootstrap.

Those absolute numbers are **not a production SLO**. A second CI runner produced materially faster absolute values, proving runner variance is significant and preventing false customer-latency claims.

A same-run 12-iteration phase measurement on the 250-row bound is still decision-useful because it compares phases inside the same executions:

- `record_decision`: ~**61.49%** of bootstrap p50;
- repeated `load_profile`: ~**22.24%**;
- `evaluate_row`: ~**12.89%**;
- other bootstrap work: ~**3.25%**.

Current `record_decision()` ensures the table and commits every row; `persist_and_classify()` reloads the same account profile per row. The persistence hotspot was routed to Data Reliability #238 in comment `5415862736`. Any optimization must preserve tenant binding, decision history, failure atomicity, migration/corruption guards and synchronous first-Radar truth. #337 will consume specialist evidence rather than mixing production persistence changes into the readiness PR.

## ACTIVE -> NEXT -> WAIT

### ACTIVE

1. Keep #337 reconciled against exact current `main` and fail closed on drift.
2. Keep #68 real-browser acceptance as the highest-value Web readiness proof and execute only when the required production-browser environment/account access is legitimately available.
3. Track #83 Billing RED, #333 Evaluation candidate, #292 privacy lifecycle and branch protection NO_GO without stealing owner implementation.
4. Consume #335/#289 movement so deterministic fixture coverage cannot silently regress to `UNKNOWN_NO_DATA` or be promoted before canonical/Golden proof.
5. Keep the performance evidence measurement-only inside #337; consume Data Reliability repair if/when it appears and remeasure before accepting improvement.

### NEXT

1. Consume #248/Support implementation of DB readiness, worker heartbeat/stall state, critical dependency degradation and privacy-safe support correlation; rerun executable operability acceptance.
2. Execute #68 preflight on the exact deployed canonical build: signup/login -> reload -> onboarding -> first truthful Radar -> detail/source -> workflow -> A/B negative proof -> logout/return, plus degraded/offline/partial and responsive/accessibility cases.
3. Consume #281/#327/#331 only after canonical/Golden movement; never infer zero-market from stale/unknown source coverage.
4. Reconcile #238/#319 recovery only after canonical and operational/off-disk proof changes.
5. Continue consuming #83/#333/#292 and refresh the matrix on every material owner/main movement.

### WAIT / EXTERNAL

- branch protection/ruleset/required-check settings — explicit founder authorization;
- production/provider/secrets/config mutation — explicit authorization;
- real FCM/EAS configuration and physical-device push acceptance — Notification/Mobile/Golden external boundary;
- real production-browser interaction when legitimate credentials/interactive environment are unavailable;
- provider/off-disk backup guarantees and production recovery operations — operator/external boundary;
- GitHub Dependency Graph enablement — repository setting required before Dependency Review can be proven.

`REPAIRABLE != BLOCKED`, `OTHER_OWNER != STOP`, `GREEN PR != READY`.

## Commands

Release matrix with fresh main verification:

```bash
python production_readiness.py --current-main-sha "$(git rev-parse origin/main)"
```

Operability acceptance:

```bash
python operability_acceptance.py \
  --current-main-sha "$(git rev-parse origin/main)" \
  --require-ready
```

#68 browser preflight audit:

```bash
python web_production_browser_preflight.py \
  --current-main-sha "$(git rev-parse origin/main)" \
  --require-go
```

Disposable measurement only:

```bash
python measure_first_value_latency.py --iterations 20
python measure_bootstrap_phases.py --iterations 12
```

None of these commands merges, deploys, changes settings/config/secrets, promotes a queue/capability/source or substitutes for explicit authorization.
