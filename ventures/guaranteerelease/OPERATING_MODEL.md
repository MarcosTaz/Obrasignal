# GuaranteeRelease — Assisted Offer & Minimum Operation

Date: 2026-08-29
Status: PILOT DESIGN — NOT COMMERCIAL PROOF

## Offer

### Security Release Recovery Audit

Customer provides an export of open guarantees/bonds plus governing contracts and project evidence. GuaranteeRelease reconstructs the security lifecycle and returns an evidence-backed queue of:

- security still valid and correctly required;
- reduction potentially due;
- release potentially due;
- evidence-supported reduction/release;
- upcoming auto-extension or expiry risk;
- missing release/cancellation documentation;
- bank/surety implementation not yet verified;
- collateral/facility restoration not yet verified;
- verified historical outcomes.

The product must make `€0 valid release` visible as a successful truth outcome when security is still legitimately required.

## Pilot eligibility

A portfolio is pilot-fit when all are true:

1. Customer can supply an instrument register or bank/surety export.
2. At least one governing contract or security clause is available per candidate instrument.
3. Relevant milestone/payment/acceptance evidence can be supplied for a meaningful subset.
4. Customer identifies an authorized treasury/commercial owner for action.
5. GuaranteeRelease is not asked to issue, amend, call, cancel or hold an instrument without customer authorization.

Preferred initial profile:

- >= 20 live instruments or >= EUR 10m equivalent security exposure;
- construction/EPC/infrastructure contractor;
- multiple banks/sureties or facilities;
- active new-work pipeline where financial-security capacity matters.

## Minimum operation

### Stage 1 — Ingest

Required fields:

- company / tenant
- project
- contract
- beneficiary
- issuer / bank / surety
- instrument id
- instrument type
- original amount
- current amount
- currency
- issue date
- expiry date
- auto-extension rule
- facility / collateral if known
- commission / premium if known

Truth rule: missing values remain `UNKNOWN`.

### Stage 2 — Link contract truth

Extract or record:

- release condition
- reduction condition
- release timing
- reduction schedule
- beneficiary action required
- original-document return required
- notice rule
- claim/defect/final-account blockers
- amendment hierarchy

No contract evidence → no fabricated entitlement.

### Stage 3 — Link project truth

Evidence classes:

- payment certificates / advance repayment
- practical completion
- provisional acceptance
- final acceptance
- final certificate
- defects/warranty period
- defect notices/resolution
- final account
- open claims
- release letter

Each evidence object must identify tenant, project, contract, date and source.

### Stage 4 — Independent classification

Allowed high-level outputs:

- REQUIRED
- REDUCTION_NOT_YET_DUE
- REDUCTION_MAY_BE_DUE
- REDUCTION_EVIDENCE_SUPPORTED
- REDUCTION_REQUESTED
- REDUCED
- RELEASE_NOT_YET_DUE
- RELEASE_MAY_BE_DUE
- RELEASE_EVIDENCE_SUPPORTED
- RELEASE_REQUESTED
- BENEFICIARY_REVIEW
- DISPUTED
- EXPIRED_BY_DATE
- EXPIRY_NOT_SUFFICIENT_FOR_RELEASE
- BANK_CANCELLED
- SURETY_CANCELLED
- COLLATERAL_RELEASED
- LIMIT_RESTORED
- VERIFIED_RELEASE
- UNKNOWN

### Stage 5 — Action queue

Priority score is decision support, not entitlement proof.

Suggested factors:

- evidence-supported reducible/releasable amount
- time to auto-extension / renewal
- known annual fee or premium
- known cash collateral
- known facility pressure
- evidence completeness
- blocker complexity
- dependency owner

Never rank an unknown right as if it were a confirmed entitlement.

### Stage 6 — Human review

Before any external action:

- verify instrument identity;
- verify governing amendment/version;
- verify evidence belongs to correct project/contract;
- verify no open claim/defect/final-account blocker was missed;
- verify requested amount does not exceed evidence-supported amount;
- obtain customer authorization.

### Stage 7 — Evidence package

For each authorized action generate:

- instrument summary
- contractual clause/reference
- milestone/evidence list
- requested reduction/release amount
- unresolved assumptions
- blocker state
- customer approval record

No legal conclusion beyond supported contract evidence; escalate ambiguity for legal review.

### Stage 8 — Verify downstream result

A request is not an outcome.

Track separately:

- beneficiary agreed
- release letter received
- bank/surety cancellation confirmed
- current amount changed
- facility utilization changed
- cash collateral released
- fees actually ceased/changed

### Stage 9 — Economic truth

Report separately:

- nominal security reduced
- nominal security cancelled
- cash collateral released
- facility limit restored
- bonding capacity restored
- directly evidenced fee/premium saving

Do not sum these unlike values into a fake "cash recovered" number.

## Commercial hypothesis

Initial pricing to test, not assert:

- Portfolio diagnostic: fixed fee.
- Recovery audit: fixed fee scaled by portfolio size/complexity.
- Verified implementation: per-instrument success fee.
- Liquid cash collateral / directly evidenced fee savings: optional percentage success fee.
- Continuous monitoring: recurring subscription.

Avoid charging a large percentage of nominal capacity as though nominal security were cash.

## Minimum web product

P0 screens:

1. Portfolio dashboard
2. Instrument register
3. Contract/release condition record
4. Evidence record
5. Release/reduction assessment
6. Action queue
7. Outcome verification
8. Executive report
9. Audit history

P0 safety:

- synthetic/demo data visibly labeled;
- tenant isolation;
- fail closed on wrong project/contract/amendment;
- potential != verified;
- expiry != release;
- cancellation != collateral release;
- no external request without customer approval.

## Current terminal

CURRENT_TERMINAL = T0 — THESIS SURVIVED (NARROWED)
NEXT_TERMINAL = T1 — PILOT CAPABLE

T1 requires a working minimum product plus oracle/red-team pass. It does not require a real customer yet.
