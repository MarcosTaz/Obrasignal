# Production & Customer Readiness Factory

Status: **EVIDENCE / READINESS ORCHESTRATION ONLY — NOT MERGE OR DEPLOY AUTHORIZATION**

Canonical snapshot: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`. `UNKNOWN` fails closed. Candidate/Integration-Lab GREEN never becomes canonical readiness by inference.

## Current verdict

- `CURRENT_WEB_SAAS = NO_GO`
- `FULL_MULTI_CHANNEL = NO_GO`

## Current first-order truth

- **AUTH — bounded PASS:** current production Auth evidence remains valid while main is unchanged.
- **TENANT — UNKNOWN:** #335 current `8a0870f6` supplies deterministic tenant-safe test fixtures. #408 exact combined `ffb6c6e2` proves current fixture + #238 persistence GREEN on Quality/GP03/JWT/CodeQL. However #400 formally records the provider workflow GET envelope as nested `{"workflow": ...}` while Auth #289 still consumes a flat root shape. Repair belongs to Auth; do not flatten the provider contract. Real browser A/B and physical-device A→B remain open.
- **DATA — UNKNOWN:** #238 current `f34d0eab` plus #408 prove strong noncanonical persistence/fixture composition. Off-disk/provider recovery remains unproven. The first-value persistence hotspot handoff `5415862736` has no accepted optimization repair yet.
- **SOURCES — UNKNOWN:** #399 `44ca24fb` composes Web/customer truth + #327 Source Health and is Quality GREEN / Golden-handoff-ready, but #281 remains open for independent Golden + canonical proof.
- **WEB — EXTERNAL / NO_GO:** #68 remains physical-browser acceptance. CI/HTTP preconditions cannot substitute for real browser signup/login/reload/onboarding/Radar/detail/workflow/A-B/logout-return and degraded/offline/partial/accessibility observations.
- **MOBILE — UNKNOWN:** #397 `720fb55d` is exact-tree GREEN for current Mobile #322+#329 + persistence. Repository proof is not physical-device Golden.
- **NOTIFICATIONS — UNKNOWN / EXTERNAL:** #397 is repository-GREEN, but #410 shows Notification data is also a Privacy lifecycle dependency. FCM/EAS and physical background/killed-app delivery remain external.
- **BILLING — NO_GO:** #83 remains `3c00cff4` RED. In addition to its existing RevenueCat auth/trial matrix repair, `deleted_pending_revocation` must remain terminal against late/duplicate/out-of-order paid snapshots.
- **EVALUATION — NO_GO:** #333 remains green candidate but noncanonical and blocked on repaired Billing + Golden lifecycle composition.
- **PRIVACY — NO_GO:** #342 current `fadeb25e` provides server export/deletion/tombstone and truthfully remains PENDING. #406 `d71638f0` adds transitive account-data discovery. #410 exact Mobile/persistence + Privacy composition `52d6e697` is RED (`8 failed / 1045 passed / 2 skipped`) because `push_devices` is account-private and Notification has not yet defined export/deletion/retention semantics for `push_devices`/`push_deliveries`. Do not weaken this failure or claim COMPLETE.
- **RECOVERY — NO_GO/UNKNOWN:** repository backup/restore mechanics remain candidate-only; provider/off-disk and customer/provider recovery are not proven.
- **SECURITY — NO_GO:** `main` remains `protected=false` with no required checks/rulesets; settings mutation requires founder authorization.
- **OBSERVABILITY — UNKNOWN:** #381 `e7d92603` proves CORE #314 + Support #355 integration-preproof GREEN, but canonical DB readiness, worker heartbeat/stall state, critical-dependency readiness, privacy-safe opaque correlation, metrics and alerting remain unimplemented/unproven.
- **GOLDEN/CUSTOMER_PROOF — NO_GO:** no single exact canonical deployed tree yet proves the full minimum sellable, supportable and recoverable customer spine.

## Executable operability acceptance

`operability_acceptance.py` encodes:

- liveness != readiness;
- DB `DEGRADED/UNAVAILABLE/UNKNOWN` => `NO_GO`;
- worker `DEGRADED/STALLED/UNAVAILABLE/UNKNOWN` => `NO_GO`;
- critical dependency `DEGRADED/UNAVAILABLE/UNKNOWN` => `NO_GO`;
- unsafe/unknown support correlation => `NO_GO`;
- even full operability READY != release GO.

Runtime implementation gaps remain routed to #248/Support ownership. #337 does not duplicate those owners.

## #68 browser preflight

`web_production_browser_preflight.py` + JSON require one exact deployed build and privacy-safe evidence. Any required FAIL/UNKNOWN/BLOCKED_EXTERNAL, conditional skip, build mismatch, tenant leak, unsafe evidence capture or false empty/degraded state keeps #68 `NO_GO`. Saved/watch is not current RC1 scope unless it becomes canonical; #352 future self-service Web purchase is separate.

## First-value measurement

The measured synchronous path is:

`POST /api/v1/profile -> save_profile -> bootstrap_account -> immediate GET /api/v1/radar`

Absolute CI timings vary enough that they are **not production SLOs**. The stable phase finding across runs is that per-row `record_decision`/commit dominates bootstrap, followed by repeated profile loads. Any specialist optimization must preserve tenant binding, complete decision history, rollback/atomicity, migration/corruption guards and truthful first Radar, then be remeasured with the same contract.

## ACTIVE -> NEXT -> WAIT

### ACTIVE
1. Keep #337 exact-main and fail-closed.
2. Keep #68 physical-browser acceptance open as `EXTERNAL / NO_GO`.
3. Consume #83/#333/#342/#406/#410/#335/#408/#399/#397 movement without stealing owner work.
4. Preserve branch-protection NO_GO until authorized settings change.
5. Keep first-value work measurement-only until Data Reliability produces a legitimate repair.

### NEXT
1. Consume #248/Support runtime readiness/correlation implementation and rerun operability acceptance.
2. Execute #68 physical browser proof when legitimate interactive credentials/environment exist.
3. Consume Notification lifecycle semantics for `push_devices` + `push_deliveries`, then retest Privacy composition; unresolved semantics remain PENDING/BLOCKED.
4. Consume Billing anti-resurrection repair for `deleted_pending_revocation`, then compose with Privacy/Golden.
5. Consume Auth #289 nested workflow parser repair and rerun FULL deterministic fixture journey.
6. Consume any #238 performance repair and remeasure.
7. Consume #281 only after canonical + independent Golden source-health acceptance.

### WAIT / EXTERNAL
- branch protection/rulesets/required checks: founder authorization;
- production/provider/secrets/config mutation: explicit authorization;
- #68 physical browser when no legitimate interactive access exists;
- FCM/EAS + physical-device notification acceptance;
- provider/off-disk backup guarantees + production recovery;
- provider identity/session revocation and external Billing reconciliation;
- Dependency Graph enablement.

`REPAIRABLE != BLOCKED`. `OTHER_OWNER != STOP`. `GREEN PR != READY`.

No merge/deploy/prod/config/secrets/settings/queue/capability/source promotion is authorized by this contract.
