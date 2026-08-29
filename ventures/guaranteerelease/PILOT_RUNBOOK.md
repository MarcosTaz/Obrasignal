# GuaranteeRelease — Controlled Pilot Runbook

Date: 2026-08-29
Status: CONTROLLED PILOT PROCEDURE — NOT PRODUCTION AUTHORITY

## Purpose

Run a contractor-side security release/reduction audit without allowing the application, operator or reviewer to manufacture contractual rights, issuer cancellation, collateral release, restored capacity, savings, customer proof or revenue. The pilot is assisted evidence/decision support. It does not issue guarantees, hold collateral, lend, or contact a beneficiary/bank/surety automatically.

## Roles

**Operator** may create/update instrument records and submit evidence as `PENDING`. Operator may not approve evidence or assert server-controlled verified states.

**Reviewer** must be a distinct configured principal. Reviewer may approve/reject eligible `PENDING` evidence after checking the retained source. Reviewer may not create/update instruments or submit evidence.

**Customer authorization owner** controls any external or irreversible action, including release/reduction requests, beneficiary communication, bank/surety communication, original-document return or cancellation instruction. The current app performs none of those actions automatically.

## Preconditions

1. Use a dedicated tenant for the pilot customer.
2. Configure at least one operator and one separate reviewer with high-entropy bearer tokens; only SHA-256 token digests are configured in the server.
3. Duplicated principal identities or token hashes must fail closed.
4. Preserve a checksum-verified backup before material pilot work.
5. Define customer-authorized projects/contracts/instruments and source repositories in scope.
6. The customer must retain the underlying documents. `sourceRef` is a locator, not the evidence bytes themselves.
7. Do not ingest real customer material until the deployment/storage/security boundary is explicitly approved for that customer.

## Workflow

### 1. Create candidate instrument

Record instrument id, company, project, contract, type, currency, original/current amount and expiry when applicable. Expected initial state is `UNKNOWN`: entered data is not evidence.

### 2. Submit reviewed baseline

Operator submits `INSTRUMENT_TERMS` tied to a retained source. It remains `PENDING`. Reviewer compares instrument type, currency, original/current amount and expiry to the current record. Mismatch cannot be approved.

If a baseline field changes later, the prior baseline becomes stale and the case returns to `UNKNOWN` until a new matching baseline is approved.

### 3. Submit only what the source proves

Supported evidence classes are `REDUCTION_RULE`, `REPAYMENT`, `MILESTONE`, `RELEASE_CONDITION`, `RELEASE_EVENT`, `BLOCKER`, `BANK_CANCELLATION`, `SURETY_CANCELLATION`, and `COLLATERAL_RELEASE`. One class must never imply another.

Reject evidence when source identity is wrong/ambiguous, the source is superseded, project/contract mismatches, the source does not establish its payload, the source cannot be retained/retrieved, or material amount/currency/date interpretation is unresolved. Unknown stays `UNKNOWN`.

### 4. Interpret assessment conservatively

- `REDUCTION_EVIDENCE_SUPPORTED`: reduction candidate supported; implementation not verified.
- `RELEASE_EVIDENCE_SUPPORTED`: release candidate supported; issuer cancellation not verified.
- `BANK_CANCELLED` / `SURETY_CANCELLED`: issuer cancellation evidenced; collateral/capacity restoration remains separate.
- `VERIFIED_RELEASE`: only the specific downstream outcome evidenced; do not infer unlike economic effects.
- zero and `*_NOT_YET_DUE` can be correct outcomes.
- `UNKNOWN` is a hard truth boundary, not an estimate request.

### 5. External-action gate

Before any real request is sent, a customer-authorized human must review the evidence package, recipient and authority. No external action may be represented as sent unless an authorized party actually sent it.

### 6. Verify downstream outcome separately

Keep separate: actual security reduction, issuer cancellation, collateral returned, bank limit restored, bonding capacity restored and fees avoided. Do not sum unlike economic values blindly.

## Case-level P0 hold conditions

Return to `UNKNOWN` / manual hold for tenant/project/contract mismatch; stale/superseded governing terms; contradictory evidence; unreviewed/stale baseline; impossible amount/date semantics; missing distinct operator provenance for approval; unavailable retained source; or unresolved interpretation that changes entitlement materially.

## Pilot metrics

Track separately instruments loaded, reviewed baselines, correct-zero cases, supported reduction/release candidates, `UNKNOWN` cases, reviewer rejection rate, time to decision, real external actions, verified reductions/cancellations, collateral/capacity restored, evidenced fees avoided and commercial fee received.

Until real customer/outcome evidence exists: real customers = 0, real outcomes = 0, revenue = 0.

## Controlled-pilot technical success

Requires reviewed baselines before non-`UNKNOWN` decisions, operator/reviewer separation, identity mismatches fail closed, correct zeros preserved, potential never presented as verified, complete principal-attributed audit history, verified backup/restore, and no known P0/P1 in the tested flow.

This does not prove willingness to pay, typical recoverable percentage, market demand or production readiness.
