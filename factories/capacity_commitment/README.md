# Capacity Commitment — T1 Assisted Recoverability

Status: **T1 IN PROGRESS / NOT YET PILOT CAPABLE**

Engine version: **`capacity-recoverability-t1.4`**

This isolated lane implements the narrowed wedge validated by the Capacity Commitment Factory:

> automotive supplier volume shortfall and dedicated-investment recoverability assurance.

It is deliberately not a forecasting, S&OP, ERP, CLM, or generic claims replacement.

## Truth invariants

1. Economic exposure is not entitlement.
2. Recoverable/claimable is not recovered, settled, invoiced, or paid.
3. Forecast-only volume is never promoted into a firm commitment.
4. Ambiguous or missing contract/evidence/integrity states fail closed.
5. Mitigation and prior customer payments reduce exposure before recoverability.
6. Shared capex is not treated as dedicated capex.
7. Fully amortized/already-paid cost cannot become a new recovery.
8. Duplicate claims are blocked.
9. Wrong program, period, currency, unit, actual completeness/deduplication, cancelled-order reconciliation, amortization basis, notice window, current contract, or amendment review block claimability.
10. An asserted verified notice window requires a persisted canonical `YYYY-MM-DD` deadline.
11. Expired notice/deadline means zero claimable amount.
12. Correct zero recovery is a successful result.
13. Positive recoverability still requires authorized human review before any external submission.
14. Historical state is checksummed, tenant-bound, engine-version-bound, and cannot be silently reinterpreted by a later engine.

## Domain path

`contract/nomination anchor -> commitment -> forecast context (non-entitlement) -> actual consumption -> exposure -> mitigation/prior payment -> integrity -> contractual/commercial right -> evidence -> verified notice window/deadline -> recoverability -> assisted package -> human review`

## Implemented T1 capabilities

- deterministic fail-closed recoverability engine;
- unit-amortized dedicated capex/tooling exposure;
- direct unrecovered NRE;
- direct unused labor capacity;
- direct committed material exposure;
- mitigation/reuse and prior payment/customer-credit reconciliation;
- strict program/period/currency/unit/actual/amortization/contract/amendment/notice integrity gates;
- independent frozen synthetic oracle with positive, zero, non-recoverable, expired and unknown outcomes;
- truth-preserving recovery/action package with evidence, missing evidence, reasons, deadline and next actions;
- `verified_recovery=false` and `payment_received=false` on generated packages;
- checksummed state snapshots with contract/nomination and separate forecast context;
- durable tenant-scoped SQLite persistence;
- duplicate create protection: same tenant + case ID cannot silently overwrite prior state;
- save -> close/reopen repository -> return with state preserved;
- backup/restore with corruption and engine-version drift rejection before live mutation;
- tenant isolation tests;
- isolated authenticated Flask assisted API;
- production tenant resolver using the repository's verified JWT provider identity and refusing unauthenticated development identity;
- request-size, schema, numeric, boolean and unknown-field hardening;
- explicit create-intent header requirement;
- authenticated assisted operator console;
- no-store, CSP, anti-framing and related response security headers;
- end-to-end synthetic assisted journey tests;
- root test wiring into the repository's exact-head Python quality job.

## Synthetic oracle / red team

The independent case matrix includes:

- full, minor and major volume outcomes;
- program delay, cancellation and partial cancellation;
- firm, flex, ambiguous and forecast-only commitment states;
- dedicated/shared capex, tooling, NRE, labor and material;
- mitigation, reuse and prior customer credit;
- duplicate claim;
- wrong program/period/currency/unit;
- missing/late call-off, duplicate volume and cancelled-order contamination;
- wrong/unknown amortization basis verification;
- unverified/unknown notice window;
- superseded contract and unreconciled amendment;
- expired or unknown notice validity;
- prior payment/mitigation exhausting exposure;
- correct zero-recovery outcomes.

The production evaluator never computes its own expected oracle values.

## Persistence and audit discipline

Authoritative persisted state is source input, not derived recovery output. Results/packages are recomputed from the stored source state only when the stored engine version matches the active engine. Version drift requires explicit reassessment instead of silent reinterpretation.

A verified notice window must carry a persisted canonical absolute deadline. Evidence-supported state requires at least one persisted evidence reference. Blank and duplicate evidence references are rejected.

## Authentication and isolation

The standalone assisted runtime requires:

- a durable DB path;
- the existing provider-mode JWT verification path;
- an authenticated account/tenant identity.

There is intentionally no production fallback to the repository's unauthenticated development account identity. Test-only tenant headers exist only in test application factories and are not the production runtime resolver.

## Verification

The repository's existing `.github/workflows/quality.yml` runs root `test_*.py` files on every pull request and checks the exact PR HEAD.

Capacity Commitment's Python suite is part of that root run. The repository-wide mobile job currently has an unrelated Expo Doctor dependency drift: Expo expects `react-native 0.86.3` while the unchanged mobile project pins `0.86.2`. This lane does not modify mobile dependencies or treat that external red job as a Capacity Commitment pass.

## Still not implemented / not proven

- automatic contract/amendment/document extraction from raw customer files;
- source-file upload/storage and page/line provenance extraction;
- mutable post-create case editing with explicit revision history (T1 is intentionally create-only to avoid silent overwrite);
- automated external customer submission;
- settlement/payment reconciliation from a real customer workflow;
- production deployment of this isolated assisted runtime;
- real-customer dataset verification;
- customer willingness-to-pay or commercial proof.

## T1 promotion gate

Do **not** claim `T1 PILOT CAPABLE` until all of the following are simultaneously true:

1. exact current Capacity Commitment HEAD Python quality job is green;
2. synthetic oracle and end-to-end assisted matrix are green;
3. no known applicable P0/P1 remains in the create-only assisted journey;
4. tenant isolation, save/return, backup/restore, evidence anchoring, notice/deadline integrity and recovery-package truth survive end-to-end validation;
5. any repository-wide unrelated failing job is explicitly evidenced and not caused by this lane;
6. README and PR description match repository truth.

No merge is authorized by this Factory lane.
