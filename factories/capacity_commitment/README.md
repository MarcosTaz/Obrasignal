# Capacity Commitment — T1 Assisted Recoverability

Status: **T1 — PILOT CAPABLE / CURRENT HARDENED ENGINE VERIFIED**

Engine version: **`capacity-recoverability-t1.12`**

Historical T1 promotion remains valid: the original candidate passed its frozen gate and established the controlled assisted product. The live T2/T3 branch has since reopened T1 repeatedly whenever a new P0/P1 was discovered, preserved failing-before evidence, repaired the defect and required exact-head Python verification before returning to market work.

Latest validated code/test head before this documentation reconciliation:

- `996473147b623a677b6879fc028a5534db08017b`
- `ObraSignal Quality` run `33270658282`
- exact revision checkout: SUCCESS
- compile: SUCCESS
- repository Python suite: **949 passed / 2 skipped / 2 warnings**
- mobile: independently red on the existing unrelated Expo dependency drift; no whole-repository green claim is made

This isolated lane implements the narrowed wedge validated by the Capacity Commitment Factory:

> automotive supplier volume shortfall and dedicated-investment recoverability assurance.

It is deliberately not a forecasting, S&OP, ERP, CLM, or generic claims replacement.

## Truth invariants

1. Economic exposure is not entitlement.
2. Recoverable/claimable is not recovered, settled, invoiced, or paid.
3. Forecast-only volume is never promoted into a firm commitment.
4. Ambiguous or missing contract/evidence/integrity states fail closed.
5. Mitigation and prior customer recovery/payments reduce exposure before recoverability and must be explicitly reviewed.
6. Shared capex is not treated as dedicated capex; dedication must itself be verified.
7. Fully amortized/already-paid cost cannot become a new recovery without the corresponding reviewed source state.
8. Duplicate claims are blocked, and a positive position additionally requires explicit duplicate-claim review; absence of a known duplicate is not proof that duplicate review occurred.
9. Wrong or unknown customer, program, period, currency, unit, actual completeness/deduplication, cancelled-order reconciliation, amortization basis, contract, amendment, notice window, asset dedication, mitigation, prior recovery or duplicate-review state blocks claimability where material.
10. A FIRM/FLEX volume commitment with zero effective committed units is not a positive recoverable volume commitment.
11. A definitive zero cannot be manufactured from unverified actuals/amortization, mitigation or prior recovery; material uncertainty remains `UNKNOWN`.
12. An asserted verified notice window requires a persisted canonical `YYYY-MM-DD` deadline and every generated review package carries an explicit assessment date.
13. A verified deadline that is before the assessment date is re-evaluated as expired without mutating the source snapshot.
14. Temporal assessment uses an explicit/injected date or a UTC-derived runtime date rather than host-local timezone accident.
15. Monetary/quantity inputs entering through the API are exact decimal strings or integers; binary JSON floats are rejected instead of silently rounded.
16. Engine Decimal arithmetic runs inside a fixed isolated context and rejects arithmetic outside the supported range as invalid input.
17. Currency codes are restricted to three ASCII alphabetic characters to avoid visually confusable/non-ISO-style identifiers.
18. Correct zero recovery is a successful result when its zero-producing inputs are sufficiently verified.
19. Positive recoverability still requires authorized human review before any external submission.
20. Historical state is checksummed, tenant-bound, engine-version-bound and structurally exact for schema v2; known nested fields cannot disappear silently.
21. Exact retries are idempotent; changed retries and concurrent changed creates cannot overwrite the first accepted state.
22. Repository case IDs use one canonical URL-addressable policy across API, persistence, list/load and restore.
23. Backup/restore preserves the canonical table contract and cannot import weaker source schema, custom triggers/indexes/foreign keys, corrupted identities, wrong engine state, or a same-physical-file alias.
24. Recovery packages are independent truth boundaries: stale results, absent required evidence, incomplete verified-notice temporal context and fabricated expiry context are rejected even for direct callers.
25. Delivery reports recompute the expected package from current persisted state and cannot render stale or post-build-mutated recovery/payment truth.

## Domain path

`company -> customer -> program -> contract/nomination -> commitment -> capacity/investment -> forecast context (non-entitlement) -> actual consumption -> exposure -> mitigation/prior recovery -> duplicate review -> integrity -> contractual/commercial right -> evidence -> verified notice window/deadline -> assessment date -> recoverability -> assisted package -> human review -> save/return`

## Implemented T1 capabilities

- deterministic fail-closed recoverability engine with isolated Decimal arithmetic context;
- unit-amortized dedicated capex/tooling exposure;
- direct unrecovered NRE, unused labor capacity and committed material exposure;
- mitigation/reuse and prior payment/customer-credit reconciliation;
- explicit review gates for mitigation, prior recovery and duplicate-claim search;
- strict customer/program/period/currency/unit/actual/amortization/asset-dedication/contract/amendment/notice integrity gates;
- zero-effective-commitment and zero-exposure integrity gates;
- independent frozen synthetic oracle with positive, zero, non-recoverable, expired and unknown outcomes;
- truth-preserving recovery/action package with evidence, missing evidence, reasons, deadline, assessment date and next actions;
- `verified_recovery=false` and `payment_received=false` on generated packages;
- package direct-call validation for current-result binding, evidence and temporal context;
- dynamic verified-deadline expiry from an explicit/UTC assessment date;
- checksummed schema-v2 state snapshots with exact top-level and nested recovery-case field sets;
- durable tenant-scoped SQLite persistence;
- canonical URL-addressable case IDs across web/repository/restore;
- exact retry idempotency and changed/concurrent duplicate-create protection;
- save -> close/reopen repository -> return with state preserved;
- backup/restore with canonical column/type/NOT-NULL/primary-key contract, no unexpected triggers/indexes/foreign keys, row validation before mutation and same-file-alias rejection;
- tenant isolation tests;
- isolated authenticated Flask assisted API;
- production tenant resolver using the repository's verified JWT provider identity and refusing unauthenticated development identity;
- request-size, exact-decimal, schema, numeric-range, boolean, currency and unknown-field hardening;
- explicit material API fields instead of truth-bearing financial/default assumptions;
- explicit create-intent header requirement;
- authenticated assisted operator console with material gates defaulting to Unknown, including duplicate review;
- no-store, CSP, anti-framing and related response security headers;
- buyer-ready Markdown report with source-text injection hardening and current assessment/duplicate-review truth;
- end-to-end synthetic assisted journey tests;
- forecast revision/extreme-forecast invariance tests;
- timeout-style retry and concurrent-create tests;
- root test wiring into the repository's exact-head Python quality job;
- explicit `T1_GATE.md` P0/P1 decision matrix.

## Synthetic oracle / red team

The independent case matrix includes:

- full, minor and major volume outcomes;
- program delay, cancellation and partial cancellation;
- firm, flex, ambiguous, zero-effective and forecast-only commitment states;
- dedicated/shared capex, tooling, NRE, labor and material;
- mitigation, reuse and prior customer credit;
- duplicate claim plus unreviewed/unknown duplicate-review state;
- wrong customer/program/period/currency/unit;
- missing/late call-off, duplicate volume and cancelled-order contamination;
- wrong/unknown amortization basis verification;
- unverified/unknown asset dedication;
- mitigation review missing/unknown;
- prior recovery review missing/unknown;
- unverified/unknown notice window and time-elapsed verified deadlines;
- wrong/superseded contract;
- unreconciled/wrong amendment;
- expired or unknown notice validity;
- prior payment/mitigation exhausting exposure without upgrading uncertainty to a false zero;
- revised/extreme forecast without entitlement drift;
- ambient Decimal precision/traps isolation and out-of-range arithmetic rejection;
- Unicode/confusable currency rejection;
- exact retry, changed duplicate and concurrent changed create;
- strict snapshot schema, corrupted restore schema and same-file backup/restore aliases;
- restart, backup and restore;
- correct zero-recovery outcomes.

The production evaluator never computes its own expected oracle values.

## Persistence and audit discipline

Authoritative persisted state is source input, not derived recovery output. Results/packages are recomputed from stored source state only when the stored engine version matches the active engine. Version drift requires explicit reassessment instead of silent reinterpretation.

Schema v2 snapshots require the exact canonical top-level field set and exact current `RecoveryCase` field set. A checksum that has been recomputed around a structurally changed payload does not make the changed schema acceptable; structural drift requires explicit migration.

A verified notice window must carry a persisted canonical absolute deadline. Runtime processing derives an assessment date and re-evaluates elapsed verified deadlines before producing a package/report. Evidence-supported state requires at least one persisted evidence reference. Blank and duplicate evidence references are rejected.

T1 is intentionally create-only. Exact repeated submission of the same snapshot is idempotent; a different source snapshot for the same tenant/case conflicts. This preserves commitment history and gives a safe recovery path after a client timeout.

## Authentication and isolation

The standalone assisted runtime requires:

- a durable DB path;
- the existing provider-mode JWT verification path;
- an authenticated account/tenant identity.

There is intentionally no production fallback to the repository's unauthenticated development account identity. Test-only tenant headers exist only in test application factories and are not the production runtime resolver.

## Verification discipline

The repository's existing `.github/workflows/quality.yml` runs root `test_*.py` files on pull-request heads and checks the exact revision under test.

The latest validated code/test head listed above passed **949 tests / 2 skipped / 2 warnings**. Every later documentation/state successor is still required to pass exact-head Python quality before being treated as the current verified branch.

The repository-wide mobile job remains independently red because current Expo Doctor expects a different React Native dependency than the unchanged mobile project pins. Capacity Commitment does not modify mobile dependencies or treat that external red job as a Capacity Commitment failure/pass.

## T2+ work — not T1 blockers

Manual contract review is explicitly acceptable for the controlled assisted T1/T3 journey. Therefore the following remain later-stage work unless real-case evidence makes one a P0/P1:

- automatic contract/amendment/document extraction from raw customer files;
- automatic page/line provenance extraction;
- mutable post-create case editing with explicit revision history;
- automated external customer submission;
- settlement/payment reconciliation from a real customer workflow;
- production-hosted public/self-service deployment of this isolated assisted runtime;
- real-customer dataset verification;
- customer willingness-to-pay or commercial proof.

## Terminal discipline

`T1 — PILOT CAPABLE` means the assisted product is technically capable of running a controlled pilot. It does **not** mean market exposed, real-customer proven, paid, or repeatable.

`APP/TEST GREEN != MARKET VALIDATION`.

The detailed decision basis lives in `T1_GATE.md`. Any new applicable P0/P1 or failed Capacity Commitment exact-head regression immediately reopens T1 before market progression continues.

No merge is authorized by this Factory lane.