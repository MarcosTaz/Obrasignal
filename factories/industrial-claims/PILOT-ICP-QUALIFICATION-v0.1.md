# Industrial Claims — Pilot ICP & Qualification Screen v0.1

Purpose: define a narrow, document-first qualification gate for an assisted pilot. This file names no real prospect and authorizes no outreach.

## Ideal pilot profile

Prioritize an industrial buyer/manufacturer that has:

- recurring supplier spend with identifiable purchase orders, invoices and receiving/acceptance records;
- negotiated commercial terms beyond simple list-price purchasing;
- at least one suspected supplier-side economic leakage category that can be reconstructed from documents;
- internal access to procurement/AP/operations evidence needed to reconcile a transaction;
- a reviewer who can distinguish commercial facts from legal interpretation;
- enough transaction value for a recovered or prevented leakage to matter economically, without requiring speculative aggregation.

Strong initial categories:

- unsupported expedite or premium-freight surcharges;
- price/quantity variance against PO or amendment;
- duplicate or misapplied charges;
- credits/rebates/allowances evidenced in commercial documents but not reconciled;
- warranty or quality-cost contribution candidates with explicit documentary basis;
- tooling/NRE/change charges where approval and commercial allocation are documentable.

## Disqualifiers / hold conditions

Hold as `NOT_QUALIFIED` or `EVIDENCE_REQUIRED` when:

- the opportunity depends only on an employee narrative or estimate;
- no controlling order/agreement/amendment can be identified;
- the amount cannot be reconstructed from source documents;
- the issue requires a legal conclusion before a commercial candidate can even be stated;
- the material transaction identifiers conflict and cannot be resolved;
- the buyer cannot provide a human reviewer with authority to inspect the evidence;
- the only path to value requires contacting the supplier before the buyer has reviewed the candidate;
- the proposed pilot requires production credentials, bank access, or broad ERP write permissions;
- the expected value is based on multiplying an unverified single-case assumption across the supplier population.

## Qualification score

Score only documented facts. UNKNOWN scores zero; never infer a positive answer.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Transaction evidence | absent | partial | PO/invoice/receipt linked |
| Contractual/documentary basis | absent | indirect | explicit clause/approval/credit basis |
| Amount reconstructability | narrative only | partially reconstructable | fully reconstructable |
| Counterparty identity | unclear | identifiable but conflicting refs | consistently identifiable |
| Human reviewer access | none | possible/unconfirmed | named internal reviewer role available |
| Evidence provenance | missing | partial | source/provenance retained |
| Commercial relevance | unquantified | bounded but small/uncertain | material bounded transaction |

Maximum: 14.

Qualification states:

- `0–5`: `NOT_QUALIFIED`
- `6–9`: `EVIDENCE_REQUIRED`
- `10–14`: `ASSISTED_PILOT_CANDIDATE`

A score never proves entitlement or recovery. It only proves pilot admissibility.

## Minimum intake before pilot work starts

Required:

1. buyer identity and internal case owner;
2. supplier/counterparty identity;
3. transaction/order identifier;
4. at least one source document establishing the transaction;
5. document or clause supporting the suspected economic discrepancy;
6. source document supporting the candidate amount or its components;
7. permission for a human reviewer to inspect the output;
8. explicit statement of missing documents/UNKNOWN facts.

If items 1–4 are absent, do not open a candidate case.

## Pilot acceptance output

The operator may return only one of:

- `NOT_QUALIFIED` — insufficient documentary basis;
- `EVIDENCE_REQUIRED` — candidate exists but required documents are missing;
- `ASSISTED_PILOT_CANDIDATE` — enough evidence exists to run the assisted forensic workflow.

The operator must also return:

- score and per-dimension reasons;
- evidence refs used;
- missing evidence;
- unresolved assumptions;
- prohibited next actions, if any;
- reviewer requirement.

## Commercial fit without fabricated ROI

Do not qualify based on unsupported claims such as “we usually recover X% of supplier spend.”

Pilot economics should be bounded from the specific admissible case only:

- known transaction value;
- reconstructable candidate amount;
- proposed fixed pilot fee or success-fee basis only after commercial approval;
- no portfolio extrapolation until multiple real cases justify it.

## T2 boundary

This ICP screen is a preparation artifact. It does not prove a named prospect, outreach, demand, willingness to pay, customer data access, entitlement, recovered money or revenue.