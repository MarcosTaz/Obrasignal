# Production & Customer Readiness Factory

Status: **EVIDENCE / READINESS ORCHESTRATION ONLY — NOT MERGE AUTHORIZATION**

This factory answers one narrow question:

> What still separates the exact canonical product from a product that can be truthfully called deployable, customer-usable, operable, recoverable and supportable?

It does not own feature implementation already assigned to Auth, Billing, Evaluation, Mobile, Notifications, Source Health, Data Reliability, Golden, Integration Lab, Assembly or another specialist. It does not own the Master Queue, capability/source promotion, deployment, production configuration, secrets, repository settings or merge authorization.

## Truth hierarchy

`GREEN CODE != INTEGRATED SYSTEM != DEPLOYED PRODUCT != REAL CUSTOMER PROOF != SUPPORTABLE SAAS`

The executable source of this factory's current release snapshot is `production_readiness_manifest.json`, validated by `production_readiness.py` and `tests/test_production_readiness.py`.

The snapshot is deliberately stale as soon as canonical `main` moves. Historical green evidence must then be reconciled rather than transferred by assumption.

## Classification

Every gate uses the same gap classification vocabulary:

- `PROVEN` — bounded evidence exists for the stated current scope;
- `UNKNOWN` — proof is insufficient; missing evidence is not success;
- `DEFECT` — a reproduced implementation or acceptance failure exists;
- `EXTERNAL` — the next legitimate proof requires an authorization, credential, provider, physical device or other external condition;
- `READY` — the gate has the evidence required by the release target, without implying merge/deploy authorization.

Release gates are separately `PASS`, `NO_GO` or `UNKNOWN`. `UNKNOWN` fails closed for release.

A branch/PR candidate, prebuild, mergeable tree, Quality green, CodeQL green or Golden result on a non-canonical tree is useful evidence but can never be promoted by this contract into production release proof.

## Release targets

Two explicit targets prevent Mobile from silently blocking a Web-only commercial release while still preserving the complete product matrix:

- `CURRENT_WEB_SAAS` — the current customer-facing Web SaaS baseline. Mobile and remote push remain visible in the full matrix but are not prerequisites for this target.
- `FULL_MULTI_CHANNEL` — adds Mobile and Notifications as blocking gates.

Changing which gates belong to either target is a product/release policy decision, not a test repair.

## Exact snapshot reconstructed 2026-08-25

Canonical `main`: `66d43f6fd51cf9cea08016dad335aaa04b711a24`.

Current-main evidence already proves bounded pieces:

- Production Smoke succeeds against the exact deployed build and provider-mode Auth health.
- Authenticated E2E succeeds for the current authenticated account spine.
- Web Preview deploys and serves the exact current-main build marker.
- Mobile Release Preflight succeeds.

These successes are intentionally insufficient for `GO`.

Current first-order release blockers/gaps include:

- **WEB — NO_GO:** issue #68 still requires the real production-configured browser journey. Shell deployment and curl checks are not browser customer acceptance.
- **BILLING — NO_GO:** PR #83 is red at its current exact head.
- **EVALUATION — NO_GO:** PR #333 repairs a real activation-path gap but is not canonical and still needs Billing composition + Golden lifecycle proof.
- **PRIVACY — NO_GO:** issue #292 records missing/unproven recovery, export and deletion customer controls.
- **RECOVERY — NO_GO:** candidate backup/restore mechanics do not yet prove the complete canonical operational and account-recovery path.
- **SECURITY — NO_GO:** visible GitHub `main` protection is disabled, no required checks are configured and no ruleset exists; applying repository settings remains an explicit founder/settings authorization boundary. Security hardening #248 is candidate evidence, not canonical proof.
- **TENANT — UNKNOWN:** current API account scoping is proven, but #277 permits a conditional detail/workflow skip when no deterministic opportunity exists; real-browser account isolation and, for Mobile, physical A-to-B isolation remain separate acceptance.
- **DATA/SOURCES/OBSERVABILITY — UNKNOWN:** strong specialist candidates exist, but their canonical/current-production release evidence is incomplete.
- **GOLDEN/CUSTOMER_PROOF — NO_GO:** the minimum sellable customer spine is not yet proven end-to-end on one exact canonical deployed release.

For the full multi-channel target, Mobile and Notifications add further physical-device/external proof requirements.

## ACTIVE -> NEXT -> WAIT

### ACTIVE

1. Keep the release matrix reconciled against exact current `main`.
2. Treat #68 real-browser acceptance as the highest-value current Web readiness proof.
3. Track #83 Billing and #333 Evaluation as owned defects; never duplicate their implementation.
4. Keep #292 account/privacy lifecycle as a hard customer-readiness gate.
5. Keep branch protection as a visible release `NO_GO` until explicitly authorized and verified.

### NEXT

1. Prove the current-main operability gap: health/readiness, privacy-safe structured failure evidence, metrics, alerting, dependency degradation, timeout/retry behavior and support diagnosis.
2. Reconcile #327/#331 source-health evidence into the release view after canonical/Golden movement.
3. Reconcile #238 recovery evidence only after its canonical integration/operational proof changes.
4. Consume #277 deterministic fixture proof once available so authenticated E2E cannot pass the full journey through a no-data skip.
5. Build exact release evidence for performance/load only after the customer-critical canonical path is stable enough to measure without weakening truth/safety.

### WAIT / EXTERNAL

- repository branch/ruleset mutation — requires explicit founder authorization;
- production/provider/secret/config mutation — requires explicit authorization;
- FCM/EAS real push configuration + physical-device acceptance — external condition owned by Notification/Mobile/Golden;
- real production-browser account interaction when credentials/interactive execution are unavailable to this factory;
- real provider/off-disk backup guarantees and production recovery operations — external/operator boundary.

`REPAIRABLE != BLOCKED`, `OTHER_OWNER != STOP`, and `GREEN PR != FINISH`: when one path is external or owned elsewhere, this factory advances the next independent readiness proof.

## Commands

Validate the contract and print every target:

```bash
python production_readiness.py
```

Machine-readable result:

```bash
python production_readiness.py --json
```

Release assertion for an explicitly selected target:

```bash
python production_readiness.py --target CURRENT_WEB_SAAS --require-go
```

`--require-go` is a release evidence assertion only. A zero exit code never merges, deploys, changes settings, promotes a queue/capability/source or substitutes for founder authorization.

## Handoff rule

For each movement:

1. reconstruct current main;
2. inspect exact specialist head/evidence;
3. classify `PROVEN / UNKNOWN / DEFECT / EXTERNAL / READY`;
4. repair only unowned readiness logic;
5. route specialist defects with exact contract/evidence;
6. retest the readiness contract;
7. reconcile the snapshot;
8. hand canonical candidates to Integration Lab / Golden / Assembly as appropriate;
9. select the next highest-value independent gap.

This document is descriptive. The manifest and executable guard are the machine-checkable anti-false-ready contract.
