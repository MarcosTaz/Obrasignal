# Production & Customer Readiness Factory

Status: **EVIDENCE / READINESS ORCHESTRATION ONLY — NOT MERGE OR DEPLOY AUTHORIZATION**

Canonical snapshot: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`. `UNKNOWN` fails closed. Candidate/Integration-Lab GREEN never becomes canonical readiness by inference.

## Current verdict

- `CURRENT_WEB_SAAS = NO_GO`
- `FULL_MULTI_CHANNEL = NO_GO`

## Current first-order truth

- **AUTH — bounded read/identity PASS only:** current production Auth read/identity boundaries remain useful evidence, but #414 proves canonical automatic `authenticated-e2e.yml` performs real production `POST /profile` and workflow write/restore round-trips on `push main` and nightly. Restore does not make that safe/non-mutating. Therefore no production-mutating E2E result is used as write-path readiness proof. Deterministic writes belong in isolated #335/#408-style integration.
- **TENANT — UNKNOWN:** #335 `8a0870f6` + #408 `ffb6c6e2` prove deterministic isolated fixture+persistence composition GREEN. #400 records canonical workflow GET nested `{"workflow":...}` vs Auth #289 flat parser BREAKING; #412 `0f8ca711` proves that governance composes GREEN without altering the contract. Auth repair + real A/B proof remain required.
- **DATA — UNKNOWN:** #238 `f34d0eab` and #408 are strong candidate evidence; off-disk/provider recovery is still unproven and no accepted first-value optimization exists.
- **SOURCES — UNKNOWN:** #399 `44ca24fb` is Web/customer truth + Source Health Quality GREEN / Golden-handoff-ready; #281 still requires independent Golden + canonical proof.
- **WEB — EXTERNAL / NO_GO:** #68 remains physical-browser acceptance. CI/HTTP cannot replace actual signup/login/reload/onboarding/Radar/detail/workflow/A-B/logout-return and degraded/offline/partial/accessibility observations.
- **MOBILE — UNKNOWN:** #397 `720fb55d` is repository GREEN for Mobile/notification/persistence; physical-device A→B remains open.
- **NOTIFICATIONS — UNKNOWN / EXTERNAL:** #410 proves Notification persistence is also a Privacy lifecycle dependency. Explicit `push_devices`/`push_deliveries` export/deletion/retention semantics and real FCM/EAS physical acceptance remain required.
- **BILLING — NO_GO:** #83 remains RED. #415 `c5e722b3` now adds the required failing-before proving `deleted_pending_revocation` must be terminal locally; its Billing Security + Quality RED is expected until the owner repairs account_registry Billing semantics. Existing RevenueCat Authorization/trial-matrix failures remain too.
- **EVALUATION — NO_GO:** #333 remains green noncanonical and awaits repaired Billing + Golden.
- **PRIVACY — NO_GO:** #342 `fadeb25e` + #406 `d71638f0` keep deletion PENDING/fail-closed. #410 remains RED on Notification lifecycle semantics; #415 now executable-proves the Billing resurrection defect. Provider identity/session revocation, device cache, historical profile cleanup and Golden also remain.
- **RECOVERY — NO_GO/UNKNOWN:** candidate backup/restore mechanics are not provider/off-disk/customer recovery proof.
- **SECURITY / CHANGE SAFETY — NO_GO:** `main` remains unprotected. In addition, #414 proves automatic canonical Auth E2E mutates production data; candidate #414 is not yet exact-head GREEN/canonical. This must be made read-only before automatic production CI can be considered safe. Branch settings remain founder authorization.
- **OBSERVABILITY — UNKNOWN:** #381 CORE+Support integration-preproof is GREEN, but #248 has not implemented canonical DB/worker/dependency/correlation readiness.
- **GOLDEN/CUSTOMER_PROOF — NO_GO:** no single exact canonical deployed tree proves the full minimum sellable/supportable/recoverable customer spine using safe evidence methods.

## Executable operability acceptance

`operability_acceptance.py` encodes liveness != readiness. DB/worker/dependency/correlation UNKNOWN or degraded/unavailable/stalled keeps `NO_GO`; even full operability READY does not equal release GO. Runtime implementation remains #248/Support ownership.

## Automatic production CI safety acceptance

`production_ci_safety.py` is an acceptance/diagnostic contract only; it does not repair #414 or own the Auth workflow.

For the current canonical `authenticated-e2e.yml` it classifies:

`UNSAFE_AUTOMATIC_PRODUCTION_WRITE`

because the same workflow is automatically triggered by `push main`/nightly, targets the production API, and contains production `POST` writes. A trap/restore block does not neutralize the mutation: a failed/interrupted run can strand changed state.

The contract distinguishes:

- `READ_ONLY_AUTOMATIC_PRODUCTION` — the required automatic-production safety state;
- `UNSAFE_AUTOMATIC_PRODUCTION_WRITE` — fail closed;
- `MANUAL_PRODUCTION_WRITE_REQUIRES_AUTHORIZATION` — not automatic, but still outside autonomous production mutation authority;
- `UNKNOWN_AUTOMATIC_TARGET` — fail closed rather than assume safety.

Run against the exact checked-out canonical workflow:

```bash
python production_ci_safety.py --json
python production_ci_safety.py --require-read-only
```

#414/Release owns the workflow repair. Deterministic write-path acceptance belongs in an isolated non-production fixture/integration environment.

## #68 browser preflight

`web_production_browser_preflight.py` + JSON require one exact deployed build and privacy-safe evidence. Required FAIL/UNKNOWN/BLOCKED_EXTERNAL, skips, build mismatch, tenant leak, unsafe evidence capture or false empty/degraded state keep #68 `NO_GO`. Saved/watch is not current RC1 unless canonical; #352 self-service purchase is separate.

## First-value measurement

The benchmark measures `POST /profile -> save_profile -> bootstrap_account -> immediate GET /radar` on disposable SQLite. Hosted-runner absolute timing varies dramatically and is **not a production SLO**. The stable signal is per-row `record_decision`/commit dominance, with repeated profile load secondary. Optimization remains #238-owned and must preserve tenant/history/atomicity/truth before remeasurement.

## ACTIVE -> NEXT -> WAIT

### ACTIVE
1. Keep #337 exact-main and fail-closed.
2. Keep #68 physical browser `EXTERNAL / NO_GO`.
3. Track #415 failing-before through Billing owner repair without touching #83 security work.
4. Track #410 Notification×Privacy lifecycle RED; never weaken completeness guards.
5. Track #414 production-mutating Auth E2E safety repair; `production_ci_safety.py --require-read-only` must fail until the exact canonical workflow is truly read-only.
6. Consume #335/#408/#400/#412 without treating integration GREEN as canonical tenant readiness.
7. Keep performance measurement separate from optimization/SLO claims.

### NEXT
1. Consume #248/Support DB readiness, worker heartbeat/stall state, dependency readiness, privacy-safe correlation, metrics/alerts; rerun operability acceptance.
2. Execute #68 physical browser proof when legitimate interactive access exists.
3. Consume Notification lifecycle semantics for `push_devices`/`push_deliveries`; retest Privacy composition.
4. Consume Billing deletion-terminal repair + existing Security repair; rerun Billing Security/full Quality; compose Privacy/Billing/Golden.
5. Consume #414 exact-head GREEN read-only automatic E2E; rerun automatic-production CI safety acceptance and route write-path proof through isolated fixture integration.
6. Consume Auth #289 nested workflow parser repair; rerun FULL deterministic fixture journey.
7. Consume any #238 performance repair and remeasure.
8. Consume #281 only after canonical + independent Golden Source Health acceptance.

### WAIT / EXTERNAL
- branch protection/rulesets/required checks: founder authorization;
- production/provider/secrets/config mutation: explicit authorization;
- #68 real browser without legitimate interactive access;
- FCM/EAS + physical-device notification acceptance;
- provider/off-disk recovery guarantees + production cutover;
- provider identity/session revocation + external Billing reconciliation;
- Dependency Graph enablement.

`REPAIRABLE != BLOCKED`. `OTHER_OWNER != STOP`. `GREEN PR != READY`.

No merge/deploy/prod/config/secrets/settings/queue/capability/source promotion is authorized by this contract.
