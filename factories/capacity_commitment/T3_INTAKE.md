# Capacity Commitment — T3 Real-Case Intake

Status: **READY FOR FIRST QUALIFIED BUYER CASE**

Purpose: receive the smallest safe dataset needed to determine whether one real automotive customer programme can enter a paid Capacity Commitment Recovery Audit.

This intake is not a claim form, legal opinion, recovery promise or broad data-room request.

## Entry gate

Do not request proprietary files until all of the following are at least plausibly true from buyer conversation:

- one real customer + one real programme can be named internally;
- a real divergence in volume/release/timing/scope occurred;
- a plausible commercial anchor exists (nomination/LTA/PO/award/minimum/flex/amortisation basis or equivalent);
- supplier-specific economic exposure may remain;
- the buyer/champion has authority to provide the bounded data or can route to someone who does;
- there is no already-established fully-paid / fully-mitigated / duplicate-zero outcome.

If these are not met, remain at eligibility/discovery. Do not create a positive recoverability claim.

## Intake identity block

Required before calculation:

- supplier legal entity;
- supplier internal programme ID/name;
- customer legal entity/business unit as used in the documents;
- customer programme / platform / part-family identifier;
- bounded analysis period start/end;
- unit of measure;
- currency;
- buyer/champion name + role;
- authorized data-transfer channel;
- known confidentiality restrictions;
- known notice/claim deadline, or `UNKNOWN`.

Identity mismatch is fail-closed. Never silently join documents from different programmes, customers, periods, currencies or units.

## Minimum document/data set

### 1. Commercial anchor

Provide the strongest applicable source(s):

- nomination / sourcing award;
- LTA / supply agreement;
- PO or blanket PO;
- minimum-volume / firm-window / take-or-pay-like term;
- tooling-amortisation or capacity-reservation basis;
- customer approval or other relevant commercial commitment.

Forecast-only demand is context, not a firm entitlement input.

### 2. Amendments and superseding terms

Provide all known changes that may alter the original basis:

- amendments;
- engineering/programme change notices;
- sourcing changes;
- cancellation / delay / phase-down / EOP notices;
- pricing or amortisation changes;
- settlement/waiver language if any.

A superseded original contract must not be treated as current by default.

### 3. Demand / actuals

For the same programme, period and unit:

- releases/call-offs;
- shipped/consumed quantities;
- forecast history only as context;
- cancelled or rescheduled quantities where relevant.

Duplicate/revised forecasts must not double count volume.

### 4. Supplier-specific investment/exposure

Only case-relevant items:

- tooling;
- dedicated cell/line/automation/capex;
- NRE / engineering / ED&D;
- committed material;
- programme-specific labour/headcount where supportable;
- other customer-specific cost basis.

Shared assets must be identified as shared. Fully amortised items must not re-enter exposure.

### 5. Amortisation / prior recovery / mitigation

Provide, where applicable:

- unit amortisation schedule;
- units already amortised;
- direct tooling/NRE reimbursements;
- customer credits/payments/settlements;
- insurance or other relevant recovery;
- asset reuse / transfer / resale;
- material reuse/resale;
- avoided cost or other mitigation relevant to net exposure.

Prior payment and mitigation are deductions, not optional context.

### 6. Notice / action history

- notice/deadline terms;
- claim or commercial request already submitted;
- customer response/dispute;
- settlement discussion;
- rejection/acceptance status;
- external counsel involvement, if any.

If legal interpretation becomes material, classify it for human/legal review rather than converting it into machine-certified fact.

## Preferred structured manifest

For every file or extract preserve:

- `source_id`;
- original filename/title;
- source type;
- customer;
- programme;
- effective date / period;
- version/amendment identity;
- received timestamp;
- supplied-by identity;
- checksum where available;
- notes on redaction or incompleteness.

Never overwrite a prior version invisibly.

## Data-minimisation rules

Do not request:

- unrelated customers;
- unrelated programmes;
- broad ERP exports when a bounded extract is sufficient;
- personal data not needed for the case;
- passwords, private keys or credentials;
- legally privileged material unless the customer expressly authorizes and a suitable review process exists.

Do not use customer data for model training without explicit permission.

## Intake outcomes

After the bounded intake review classify exactly one:

- `READY_FOR_PAID_PILOT`;
- `NEEDS_SPECIFIC_MISSING_EVIDENCE`;
- `NO_SUPPORTABLE_COMMERCIAL_ANCHOR`;
- `ZERO_EXPOSURE_OR_FULLY_RECOVERED`;
- `NOTICE_OR_LEGAL_REVIEW_REQUIRED`;
- `DATA_AUTHORIZATION_BLOCKED`;
- `IDENTITY_INTEGRITY_BLOCKED`.

Only `READY_FOR_PAID_PILOT` proceeds into the paid execution scope without another unresolved P0/P1 integrity blocker.

## Buyer-facing bounded request

When a case qualifies, request **one customer + one programme + one bounded period only**. Explain that a smaller initial dataset reduces confidentiality exposure and allows the audit to stop early if the evidence supports zero/unknown recoverability.
