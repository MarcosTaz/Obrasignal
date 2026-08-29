# Industrial Claims — Synthetic Pilot Admissibility v0.1

Purpose: repository-only test fixture for the assisted Industrial Claims pilot. No real customer, supplier, contract, invoice, claim, recovery, entitlement or payment is represented here.

## Synthetic intake fixture

Synthetic company: `SYNTHETIC-MANUFACTURER-A`
Synthetic supplier: `SYNTHETIC-SUPPLIER-B`
Synthetic commercial relationship: multi-order component supply agreement.
Synthetic evidence set:

- signed master supply agreement placeholder;
- purchase-order placeholder;
- supplier invoice placeholder;
- delivery/acceptance placeholder;
- change/expedite correspondence placeholder;
- payment ledger placeholder;
- internal claim note placeholder.

All placeholders must be generated data. No copied customer documents are permitted in this fixture.

## Admission gate

A candidate enters assisted forensic review only when all of the following are true:

- the commercial counterparty is identifiable from supplied evidence;
- the relevant transaction/order can be tied to documentary evidence;
- the suspected economic leakage has a stated contractual or documentary basis;
- the claimed amount can be reconstructed from source documents rather than inferred from a narrative alone;
- conflicting documents are retained rather than silently reconciled;
- missing evidence is represented as UNKNOWN, not filled by assumption;
- a human reviewer is required before any candidate becomes a defensible claim output.

## Fail-closed rejection reasons

Reject or hold as UNKNOWN when any of these apply:

- no controlling agreement/order can be identified;
- amount depends on an unstated rate, quantity, date or entitlement;
- evidence contains irreconcilable identifiers without a documented resolution;
- the supposed overcharge/under-recovery depends on legal interpretation not established in the evidence;
- source documents cannot be tied to the same transaction;
- the candidate is based only on an internal estimate;
- evidence provenance is missing for a material fact.

## Synthetic candidate example

Candidate ID: `SYN-IC-0001`
Category: synthetic expedite surcharge reconciliation.
Status: `NEEDS_HUMAN_REVIEW`.

Synthetic facts:

- Base order value: `100,000 synthetic currency units`.
- Invoice includes an `8,000` expedite surcharge.
- Placeholder correspondence states expedite pricing is subject to written approval.
- No written approval placeholder is supplied in the fixture.

Permitted conclusion:

`Candidate surcharge of 8,000 synthetic units requires documentary entitlement review; recoverability is NOT established.`

Forbidden conclusions:

- `8,000 is owed.`
- `8,000 is recoverable.`
- `supplier overcharged 8,000.`

## Required output contract

Every candidate output must preserve:

- candidate identifier;
- evidence references;
- documentary basis;
- reconstructed amount and formula, if supportable;
- unresolved assumptions;
- missing evidence;
- confidence classification;
- human-review state;
- explicit distinction between candidate amount and proven entitlement/recovery.

## T2 evidence boundary

This fixture proves only that a controlled synthetic admissibility path is defined. It does not prove market exposure, customer demand, legal entitlement, recovered cash, product automation or production readiness.
