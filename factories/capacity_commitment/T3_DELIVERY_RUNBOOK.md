# Capacity Commitment — T3 Real-Case Delivery Runbook

Status: **READY FOR FIRST REAL QUALIFIED CASE**

Purpose: execute a real paid/proprietary buyer case through the existing T1 pilot-capable product without weakening identity, evidence, tenant, contract, amendment, mitigation or payment truth.

## 0. Entry condition

Start only when a buyer response has reached at least one of:

- `CASE_SIGNAL_QUALIFIED`;
- `DATA_WILLINGNESS`;
- `PILOT_PRICE_REQUESTED`;
- `PILOT_ACCEPTED_UNPAID`;
- meaningful proprietary `DATA_PROVIDED` in a credible buying process.

A generic positive reply is not enough to fabricate a case.

## 1. Freeze case identity

Before ingesting documents, assign a case identity with:

- tenant / supplier legal entity;
- customer;
- programme;
- bounded period;
- currency;
- unit;
- internal case ID;
- buyer/champion;
- authorized intake route.

Any identity ambiguity is a blocking condition for calculation, not a reason to guess.

## 2. Preserve sources

For each received source:

- preserve original source name/version;
- capture source type;
- capture customer/programme/effective date;
- record received-from and received-at;
- checksum or immutable content identity where available;
- retain amendment/supersession relationship;
- record redaction/incompleteness.

Never silently replace an earlier contract, forecast or amendment with a later file.

## 3. Intake review

Use `T3_INTAKE.md` to classify:

- `READY_FOR_PAID_PILOT`;
- `NEEDS_SPECIFIC_MISSING_EVIDENCE`;
- `NO_SUPPORTABLE_COMMERCIAL_ANCHOR`;
- `ZERO_EXPOSURE_OR_FULLY_RECOVERED`;
- `NOTICE_OR_LEGAL_REVIEW_REQUIRED`;
- `DATA_AUTHORIZATION_BLOCKED`;
- `IDENTITY_INTEGRITY_BLOCKED`.

Request only the smallest missing item that can change the decision.

## 4. Human commercial-anchor review

Before positive recoverability:

- identify the strongest current applicable commercial anchor;
- determine whether it is firm, flex-window, forecast-only, ambiguous or none;
- identify superseding amendments;
- identify notice/deadline language;
- flag legal-interpretation questions for human/legal review.

The engine assists classification; it does not certify legal entitlement.

## 5. Map into the T1 recoverability engine

Map only evidence-backed values into the canonical Capacity Commitment model.

Required integrity checks include:

- same customer;
- same programme;
- same bounded period;
- same currency;
- same unit;
- actual volume completeness state;
- amortisation inputs;
- mitigation/reuse;
- prior recovery;
- notice state;
- contract/amendment identity;
- dedicated vs shared asset state.

Unknown values remain unknown. Do not coerce unknown to zero, false, fully mitigated, or recoverable.

## 6. Run calculation and classify

The result can legitimately be:

- `RECOVERABLE`;
- `NON_RECOVERABLE`;
- `EXPIRED`;
- `UNKNOWN`;
- `ZERO_EXPOSURE`.

Positive economic exposure is not automatically recoverable. Recoverable is not the same as claimed, accepted, paid or recovered.

## 7. Red-team the result before delivery

For every positive or material result, explicitly test:

- wrong customer/programme joined;
- wrong period;
- wrong unit/currency;
- duplicate/revised forecast counted twice;
- forecast promoted to firm commitment;
- missing/late call-offs;
- cancelled orders miscounted;
- shared/reusable asset treated as dedicated loss;
- fully amortised tooling reintroduced;
- mitigation/reuse omitted;
- prior customer payment/credit omitted;
- prior claim/settlement duplicated;
- amendment/supersession ignored;
- expired/unknown notice window;
- contract evidence weaker than conclusion;
- cross-tenant/source leakage;
- restart/retry/duplicate case creating inconsistent persistence.

Any applicable P0/P1 defect blocks positive external language until repaired or downgraded to unknown/non-recoverable as appropriate.

## 8. Produce buyer deliverable

Use the T1 recovery package to produce:

- executive summary;
- commitment vs actual baseline;
- exposure calculation;
- amortisation reconciliation;
- mitigation/prior recovery;
- evidence register;
- missing evidence;
- recoverability state/reasons;
- deadline/notice state;
- recommended next commercial action;
- explicit human-review boundary.

Do not expose internal test/control labels in external copy.

## 9. Review call

On the buyer review call:

- lead with the bounded conclusion;
- explain what is proven, assumed, unknown or excluded;
- show how mitigation/prior recovery changed the net result;
- identify the smallest missing evidence if outcome is unknown;
- do not pressure a positive claim when the correct result is zero;
- do not represent the service as legal counsel.

## 10. External action boundary

The buyer/internal team decides whether to:

- close the case;
- gather missing evidence;
- make a commercial request;
- route to counsel;
- negotiate;
- pursue another authorised action.

Capacity Commitment does not automatically submit a claim, accept settlement or negotiate on the buyer’s behalf.

## 11. Commercial proof ledger

Update independently:

- `REPLIED`;
- `REPLY_CLASS`;
- `QUALIFIED`;
- `CASE_EXISTS`;
- `DATA_AVAILABLE`;
- `DATA_PROVIDED`;
- `DISCOVERY`;
- `PILOT_PROPOSED`;
- `PRICE`;
- `PILOT_ACCEPTED`;
- `AGREEMENT_SIGNED`;
- `INVOICE_ISSUED`;
- `PAYMENT_RECEIVED`;
- `DELIVERABLE_SENT`;
- `BUYER_REVIEW_COMPLETED`;
- `EXTERNAL_RECOVERY_ACTION`;
- `CUSTOMER_PAYMENT_RECEIVED_BY_BUYER`;
- `OUR_REVENUE_RECEIVED`.

No state implies a stronger state.

## 12. Terminal transitions

### T3 — COMMERCIAL PROOF

Can be satisfied by meaningful proprietary case data in a credible buying process, a paid audit/pilot, signed recovery engagement or signed hybrid/success-fee agreement, consistent with the Factory canon.

### T4 — VERIFIED ECONOMIC VALUE + OUR REVENUE

Requires a real customer, real case, real evidence/data, verified economic value/recovery outcome, real commercial transaction and money actually received by us. Do not promote theoretical exposure, invoice issuance or unpaid approval to T4.

## ACTIVE after first case arrives

`CLASSIFY REPLY → FREEZE IDENTITY → BOUNDED INTAKE → COMMERCIAL-ANCHOR REVIEW → ENGINE → RED TEAM → DELIVERABLE → BUYER REVIEW → COMMERCIAL LEDGER → NEXT CASE`.
