# Industrial Claims — Synthetic Assisted Pilot Packet v0.1

Purpose: prove a repository-only, end-to-end assisted pilot path using generated placeholder evidence only. This packet is not a real customer case and does not establish entitlement, recovery, supplier fault, market demand or revenue.

## 1. Synthetic case identity

- Case ID: `SYN-IC-PILOT-0001`
- Synthetic customer: `SYNTHETIC-MANUFACTURER-A`
- Synthetic supplier: `SYNTHETIC-SUPPLIER-B`
- Transaction: `PO-SYN-2026-041`
- Candidate category: expedite surcharge reconciliation
- Operator state: `ASSISTED_REVIEW`
- Customer authorization: `SYNTHETIC_ONLY`

All names, identifiers, values and documents in this packet are generated placeholders.

## 2. Intake manifest

| Evidence ref | Placeholder | Material fact supported | Provenance state |
|---|---|---|---|
| `EV-001` | master supply agreement | written-approval condition may govern expedite pricing | `SYNTHETIC_GENERATED` |
| `EV-002` | purchase order | base order value and transaction identity | `SYNTHETIC_GENERATED` |
| `EV-003` | supplier invoice | invoiced surcharge and total | `SYNTHETIC_GENERATED` |
| `EV-004` | delivery/acceptance record | goods tied to same order | `SYNTHETIC_GENERATED` |
| `EV-005` | expedite correspondence | expedite request exists; approval requirement referenced | `SYNTHETIC_GENERATED` |
| `EV-006` | payment ledger | invoice settlement status placeholder | `SYNTHETIC_GENERATED` |
| `EV-007` | internal claim note | internal allegation only; not entitlement evidence | `SYNTHETIC_GENERATED` |
| `EV-008` | written surcharge approval | required to prove approval | `MISSING / UNKNOWN` |

No missing evidence may be fabricated from narrative context.

## 3. Evidence classification

### Controlling documentary basis

`EV-001` and `EV-002` are the candidate controlling documents for transaction identity and commercial terms.

### Transaction linkage

`EV-002`, `EV-003` and `EV-004` share `PO-SYN-2026-041`; this is sufficient for the synthetic fixture to treat them as the same transaction.

### Amount reconstruction

Generated values:

- base order value from `EV-002`: `100,000 synthetic currency units`;
- expedite surcharge from `EV-003`: `8,000 synthetic currency units`;
- invoiced total: `108,000 synthetic currency units`.

Reconstruction formula:

`candidate surcharge amount = invoiced total - base order value = 108,000 - 100,000 = 8,000 synthetic units`.

This proves arithmetic only. It does not prove that the surcharge is invalid, owed back or recoverable.

## 4. Admission decision

Admissibility status: `ADMIT_TO_HUMAN_REVIEW`.

Reasons:

- counterparty and transaction are identifiable;
- source documents can be tied to the same synthetic order;
- the candidate amount can be reconstructed directly from the invoice and PO;
- a documentary condition relevant to approval is present;
- the decisive written approval evidence is missing and is preserved as UNKNOWN.

The case is not admissible to a final claim state because `EV-008` is absent.

## 5. Candidate claim object

- Candidate ID: `SYN-IC-0001`
- Candidate amount: `8,000 synthetic units`
- Candidate status: `NEEDS_HUMAN_REVIEW`
- Documentary basis: `EV-001`, `EV-002`, `EV-003`, `EV-005`
- Missing evidence: `EV-008`
- Unresolved question: whether written approval for the surcharge exists in an authoritative source
- Confidence classification: `DOCUMENTED_AMOUNT / ENTITLEMENT_UNKNOWN`
- Proven entitlement: `UNKNOWN`
- Proven recovery: `0 / NOT ESTABLISHED`
- Supplier fault: `NOT ESTABLISHED`

Permitted operator conclusion:

`An 8,000 synthetic-unit surcharge is documentarily identifiable and arithmetically reconstructable. The evidence set indicates written approval may be material, but no approval evidence is present. Entitlement and recoverability remain UNKNOWN pending human review and missing-document resolution.`

## 6. Human review checklist

The reviewer must answer each item explicitly:

- [ ] Does the cited contract/order language actually apply to this transaction?
- [ ] Is the 8,000 amount reconstructed without unstated rates or quantities?
- [ ] Is `EV-008` genuinely missing rather than overlooked or inaccessible?
- [ ] Is there any conflicting amendment, waiver, side letter or course-of-dealing evidence?
- [ ] Does the evidence support a commercial request for clarification/reconciliation without asserting legal entitlement?
- [ ] Has any legal interpretation required for a stronger conclusion been kept outside the automated output?

If any material answer is UNKNOWN, the final state stays `NEEDS_HUMAN_REVIEW` or `EVIDENCE_REQUIRED`.

## 7. Assisted output packet

The assisted operator can produce only:

1. evidence manifest;
2. transaction linkage table;
3. reconstructed candidate amount and formula;
4. missing/conflicting evidence register;
5. human-review checklist;
6. candidate summary with explicit UNKNOWN fields;
7. optional request-for-information draft that asks for `EV-008` without alleging overcharge or entitlement.

It must not automatically produce:

- a legal claim;
- a demand for payment;
- a statement that the supplier overcharged;
- a statement that 8,000 is recoverable;
- a success-fee invoice;
- a recovery/revenue record marked PAID.

## 8. Synthetic request-for-information draft

`Please provide any written approval, amendment or other contemporaneous record authorizing the expedite surcharge associated with PO-SYN-2026-041. The current evidence set identifies an 8,000 synthetic-unit surcharge but does not contain the approval record needed to determine its contractual treatment.`

This draft is synthetic and is not authorized for external transmission.

## 9. End-to-end terminal

Synthetic path demonstrated:

`INTAKE -> EVIDENCE CLASSIFICATION -> TRANSACTION LINKAGE -> AMOUNT RECONSTRUCTION -> ADMISSIBILITY -> CANDIDATE -> HUMAN REVIEW -> EVIDENCE REQUIRED`.

Terminal for this fixture: `EVIDENCE_REQUIRED`.

A stronger terminal is deliberately blocked until the missing evidence is supplied and human review resolves the documentary question.

## 10. T2 truth boundary

This packet proves only that a fail-closed assisted workflow can carry a generated case end-to-end to a human-reviewable candidate without inventing entitlement. It does not prove a real customer, real supplier, real claim, willingness to pay, market exposure, legal validity, recovered cash, production automation or canonical application-source verification.