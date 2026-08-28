# Capacity Commitment — T1 Assisted Recoverability

Status: **T1 — PILOT CAPABLE**

Engine version: **`capacity-recoverability-t1.5`**

Promotion basis: exact candidate HEAD `bfeda970dfc9c7681d85d8a2afaccbc3dee6afe0` passed the full repository Python suite with **855 passed / 2 skipped**, and `T1_GATE.md` records no applicable known unresolved P0/P1 in the controlled create-only assisted journey. Any later regression reopens T1 immediately.

This isolated lane implements the narrowed wedge validated by the Capacity Commitment Factory:

> automotive supplier volume shortfall and dedicated-investment recoverability assurance.

It is deliberately not a forecasting, S&OP, ERP, CLM, or generic claims replacement.

## Truth invariants

1. Economic exposure is not entitlement.
2. Recoverable/claimable is not recovered, settled, invoiced, or paid.
3. Forecast-only volume is never promoted into a firm commitment.
4. Ambiguous or missing contract/evidence/integrity states fail closed.
5. Mitigation and prior customer recovery/payments reduce exposure before recoverability.
6. Mitigation and prior recovery must be explicitly reviewed before a positive position.
7. Shared capex is not treated as dedicated capex; dedication must itself be verified.
8. Fully amortized/already-paid cost cannot become a new recovery.
9. Duplicate claims are blocked.
10. Wrong customer, program, period, currency, unit, actual completeness/deduplication, cancelled-order reconciliation, amortization basis, contract, amendment, notice window, or asset-dedication state blocks claimability.
11. An asserted verified notice window requires a persisted canonical `YYYY-MM-DD` deadline.
12. Expired notice/deadline means zero claimable amount.
13. Correct zero recovery is a successful result.
14. Positive recoverability still requires authorized human review before any external submission.
15. Historical state is checksummed, tenant-bound, engine-version-bound, and cannot be silently reinterpreted by a later engine.
16. Exact retries are idempotent; changed retries and concurrent changed creates cannot overwrite the first accepted state.

## Domain path

`company -> customer -> program -> contract/nomination -> commitment -> capacity/investment -> forecast context (non-entitlement) -> actual consumption -> exposure -> mitigation/prior recovery -> integrity -> contractual/commercial right -> evidence -> verified notice window/deadline -> recoverability -> assisted package -> human review -> save/return`

## Implemented T1 capabilities

- deterministic fail-closed recoverability engine;
- unit-amortized dedicated capex/tooling exposure;
- direct unrecovered NRE;
- direct unused labor capacity;
- direct committed material exposure;
- mitigation/reuse and prior payment/customer-credit reconciliation;
- explicit review gates for mitigation and prior recovery;
- strict customer/program/period/currency/unit/actual/amortization/asset-dedication/contract/amendment/notice integrity gates;
- independent frozen synthetic oracle with positive, zero, non-recoverable, expired and unknown outcomes;
- truth-preserving recovery/action package with evidence, missing evidence, reasons, deadline and next actions;
- `verified_recovery=false` and `payment_received=false` on generated packages;
- checksummed state snapshots with contract/nomination and separate forecast context;
- durable tenant-scoped SQLite persistence;
- exact retry idempotency;
- changed duplicate create protection: same tenant + case ID cannot silently overwrite prior state;
- concurrent changed-create race protection with one persisted winner;
- save -> close/reopen repository -> return with state preserved;
- backup/restore with corruption and engine-version drift rejection before live mutation;
- tenant isolation tests;
- isolated authenticated Flask assisted API;
- production tenant resolver using the repository's verified JWT provider identity and refusing unauthenticated development identity;
- request-size, schema, numeric, boolean and unknown-field hardening;
- explicit create-intent header requirement;
- authenticated assisted operator console with material gates defaulting to Unknown;
- no-store, CSP, anti-framing and related response security headers;
- end-to-end synthetic assisted journey tests;
- forecast revision/extreme-forecast invariance tests;
- timeout-style retry and concurrent-create tests;
- root test wiring into the repository's exact-head Python quality job;
- explicit `T1_GATE.md` P0/P1 decision matrix.

## Synthetic oracle / red team

The independent case matrix includes:

- full, minor and major volume outcomes;
- program delay, cancellation and partial cancellation;
- firm, flex, ambiguous and forecast-only commitment states;
- dedicated/shared capex, tooling, NRE, labor and material;
- mitigation, reuse and prior customer credit;
- duplicate claim;
- wrong customer/program/period/currency/unit;
- missing/late call-off, duplicate volume and cancelled-order contamination;
- wrong/unknown amortization basis verification;
- unverified/unknown asset dedication;
- mitigation review missing/unknown;
- prior recovery review missing/unknown;
- unverified/unknown notice window;
- wrong/superseded contract;
- unreconciled/wrong amendment;
- expired or unknown notice validity;
- prior payment/mitigation exhausting exposure;
- revised/extreme forecast without entitlement drift;
- exact retry, changed duplicate and concurrent changed create;
- restart, backup and restore;
- correct zero-recovery outcomes.

The production evaluator never computes its own expected oracle values.

## Persistence and audit discipline

Authoritative persisted state is source input, not derived recovery output. Results/packages are recomputed from the stored source state only when the stored engine version matches the active engine. Version drift requires explicit reassessment instead of silent reinterpretation.

A verified notice window must carry a persisted canonical absolute deadline. Evidence-supported state requires at least one persisted evidence reference. Blank and duplicate evidence references are rejected.

T1 is intentionally create-only. Exact repeated submission of the same snapshot is idempotent; a different source snapshot for the same tenant/case conflicts. This preserves commitment history and gives a safe recovery path after a client timeout.

## Authentication and isolation

The standalone assisted runtime requires:

- a durable DB path;
- the existing provider-mode JWT verification path;
- an authenticated account/tenant identity.

There is intentionally no production fallback to the repository's unauthenticated development account identity. Test-only tenant headers exist only in test application factories and are not the production runtime resolver.

## Verification

The repository's existing `.github/workflows/quality.yml` runs root `test_*.py` files on every pull request and checks the exact PR HEAD.

The candidate code/docs state immediately before this terminal record passed **855 tests / 2 skipped** on exact HEAD. This terminal documentation commit is also required to pass exact-head Python quality; failure automatically reopens T1 rather than being ignored.

The repository-wide mobile job remains independently red because current Expo Doctor expects `react-native 0.86.3` while the unchanged mobile project pins `0.86.2`. This lane does not modify mobile dependencies or treat that external red job as a Capacity Commitment pass.

## T2+ work — not T1 blockers

Manual contract review is explicitly acceptable for the controlled assisted T1 journey. Therefore the following remain later-stage work unless new evidence makes one a P0/P1:

- automatic contract/amendment/document extraction from raw customer files;
- automatic page/line provenance extraction;
- mutable post-create case editing with explicit revision history;
- automated external customer submission;
- settlement/payment reconciliation from a real customer workflow;
- production market deployment of this isolated assisted runtime;
- real-customer dataset verification;
- customer willingness-to-pay or commercial proof.

## Terminal discipline

`T1 — PILOT CAPABLE` means the assisted product is technically capable of running a controlled pilot. It does **not** mean market exposed, real-customer proven, paid, or repeatable.

The detailed decision basis lives in `T1_GATE.md`. Any new applicable P0/P1 or failed Capacity Commitment exact-head regression reopens T1 before T2 may continue.

No merge is authorized by this Factory lane.
