# Capacity Commitment — T3 Conversion Playbook

Status: **ACTIVE AFTER T2 MARKET EXPOSURE**

Current terminal: **T2 — MARKET EXPOSED**
Next terminal: **T3 — COMMERCIAL PROOF**

This playbook exists to convert a real buyer response into a truthful, bounded commercial commitment without overstating entitlement, recovery, customer status, or revenue.

## T3 proof threshold

T3 is achieved only with meaningful commercial behavior such as at least one of:

- paid audit;
- paid pilot;
- signed recovery engagement;
- signed success-fee/hybrid agreement;
- meaningful proprietary case data supplied as part of a credible buying process.

The following do **not** independently prove T3:

- email delivered;
- reply;
- positive reply;
- meeting booked;
- verbal interest;
- request for more information;
- free eligibility screen;
- theoretical exposure;
- synthetic case.

## Outbound pre-send control

Every external commercial email must be re-read from the exact stored draft/message immediately before sending. Do not rely on an earlier copy or assumption about draft state.

Fail the send if any of the following are present in the external subject/body unless deliberately customer-facing:

- `HOLD`;
- `OWNER APPROVAL`;
- `DGC`;
- `COMPLIANCE`;
- `DRAFT`;
- `INTERNAL`;
- legal-channel notes;
- placeholder text;
- unsupported customer/recovery/payment claims.

Before send verify exactly:

1. recipient is the intended public/corporate route;
2. subject contains no internal control token;
3. body identifies the sender;
4. body contains a simple opt-out where required/appropriate;
5. public trigger facts are still supported and current enough for the message;
6. no public signal is promoted into a real case, entitlement, recovery or customer state;
7. country/channel compliance gate is satisfied;
8. no weekend/overnight timing assumption is used as evidence of demand or rejection.

The CT Automotive / Autins subject-prefix incident is the regression case that motivated this control.

## Reply classification

Every inbound response must be classified exactly as one of:

1. `BOUNCE`
2. `OPT_OUT`
3. `NOT_RELEVANT`
4. `WRONG_OWNER_FORWARD_REQUESTED`
5. `WRONG_OWNER_FORWARDED`
6. `INTEREST_NO_CASE`
7. `CASE_SIGNAL_UNQUALIFIED`
8. `CASE_SIGNAL_QUALIFIED`
9. `DATA_WILLINGNESS`
10. `DISCOVERY_BOOKED`
11. `PILOT_PRICE_REQUESTED`
12. `PILOT_PROPOSED`
13. `PILOT_ACCEPTED_UNPAID`
14. `PAID_PILOT`
15. `SIGNED_HYBRID_OR_SUCCESS_FEE`
16. `REJECTED_PRICE`
17. `REJECTED_TRUST`
18. `REJECTED_TIMING`
19. `REJECTED_NO_RIGHT`
20. `REJECTED_NO_DATA`
21. `REJECTED_INTERNAL_CAPABILITY`
22. `REJECTED_OTHER`

No weaker state may be promoted into a stronger one without evidence.

## 15-minute eligibility discovery

The goal is not to sell broadly. The goal is to determine whether one bounded program can enter an assisted recoverability audit.

### A. Trigger

1. Which customer/program changed?
2. What changed: volume, release timing, cancellation, phase-down, delay, sourcing or another event?
3. When did the divergence become material?

### B. Commitment truth

4. What is the strongest commercial anchor: nomination, LTA, PO, award letter, minimum volume, firm/flex window, take-or-pay, capacity reservation, tooling amortization basis, or other?
5. Was the relevant quantity firm, forecast-only, conditional or ambiguous?
6. Were there later amendments or superseding terms?

### C. Economic exposure

7. What supplier-specific investment remains potentially unrecovered: tooling, dedicated line/cell, NRE/ED&D, labor/headcount, committed material or other?
8. How much has already been amortized or reimbursed?
9. What capacity/assets/material can be reused or mitigated?
10. Has the customer already issued any credit/payment/settlement?

### D. Evidence / deadline

11. Are the commercial anchor, amendments, releases/actuals and cost basis available?
12. Is there a notice/claim deadline or contractual timing requirement?
13. Has any claim already been submitted, disputed, accepted, rejected or settled?

### E. Buying process

14. Who owns the economic decision: CFO/Finance, Commercial, Program or CEO/MD?
15. If the bounded case qualifies, can the company provide the minimum dataset under its preferred confidentiality process?

## Qualification rule

A case is `CASE_SIGNAL_QUALIFIED` only when all are true:

- real customer/program exists;
- real divergence exists;
- a plausible commercial anchor exists, though final entitlement may remain UNKNOWN;
- material supplier-specific exposure is plausible;
- data access is plausible;
- buyer/champion exists;
- there is no obvious duplicate/fully-paid/fully-mitigated zero case already established.

If contractual support is weak or absent, the case may still be economically painful but is not represented as recoverable.

## Minimum data request after qualification

Request only one customer + one program + one bounded period initially:

1. nomination/LTA/PO/award or equivalent;
2. applicable amendments;
3. commitment/minimum/flex basis;
4. forecast/release/call-off history;
5. shipped/consumed actuals;
6. tooling/capex/NRE/labor/material cost basis;
7. amortization history;
8. mitigation/reuse evidence;
9. prior customer credits/payments/recoveries;
10. notice/deadline terms;
11. claim/correspondence history if a recovery action already exists.

Do not request unrelated corporate/customer data.

## Paid pilot — default commercial proposal

### Scope

One customer + one program + one bounded period.

### Fee hypothesis

**£3,000 / €3,500 fixed assisted pilot**, subject to final scope/currency.

### Included

- commitment vs actual reconstruction;
- economic exposure calculation;
- amortization reconciliation;
- mitigation/prior-recovery reconciliation;
- contract/amendment/evidence integrity review;
- notice/deadline state;
- recoverability classification;
- evidence/missing-evidence register;
- assisted action/recovery package;
- one review call.

### Explicit exclusions

- legal representation;
- guarantee of recovery;
- litigation;
- negotiation authority unless separately agreed;
- production ERP integration;
- broad multi-program historical audit;
- automated external submission.

### Truth clause

A correct `£0 / €0 recoverable` conclusion is a valid pilot outcome. Fee pays for the bounded forensic assessment, not for manufacturing a claim.

## Hybrid alternative

Use only when buyer rejects fixed-fee risk but demonstrates a real qualified case and is willing to contract.

Hypothesis:

- **£1,250 / €1,500 setup** plus
- **7.5% of incremental cash actually received** and attributable to the supported recovery action.

Never charge a success percentage on:

- theoretical exposure;
- submitted claim value;
- disputed amount;
- approved-but-unpaid amount;
- recovery that was already contractually due and fully in process before our work unless attribution is explicitly agreed.

## Commercial proof ledger

For every target track:

- TARGET
- TRIGGER
- CONTACTED
- DELIVERED
- REPLIED
- REPLY_CLASS
- BUYER_ROLE
- QUALIFIED
- CASE_EXISTS
- COMMITMENT_TYPE
- REAL_EXPOSURE_SIGNAL
- DATA_AVAILABLE
- DISCOVERY
- DATA_REQUESTED
- DATA_PROVIDED
- PILOT_PROPOSED
- PRICE
- COMMERCIAL_MODEL
- PILOT_ACCEPTED
- AGREEMENT_SIGNED
- INVOICE_ISSUED
- PAYMENT_RECEIVED
- REJECTED
- REJECTION_REASON
- NEXT_ACTION
- EVIDENCE_REFERENCE

`INVOICE_ISSUED != PAYMENT_RECEIVED`.

## Data/security intake

Before receiving proprietary case data:

- use only an authorized channel;
- confirm customer identity/tenant;
- state bounded purpose;
- minimize requested files;
- do not mix data between Capacity Commitment and sister companies without explicit customer authorization;
- do not use customer data for model training without explicit permission;
- preserve source identity/version and evidence references;
- do not expose legal conclusions as machine-certified facts.

## Response handling SLA hypothesis

For a meaningful buyer reply:

- acknowledge same business day when operationally possible;
- answer the actual question first;
- do not send a generic deck if the buyer described a case;
- offer the 15-minute eligibility screen or request the bounded anonymized outline;
- after qualification, send the minimum data request and commercial pilot scope;
- record rejection reasons verbatim enough to learn, without overinterpreting them.

## Objection handling

### "We already have commercial/account teams for this"

Position: Capacity Commitment is an independent reconciliation/recoverability layer, not a replacement. Ask whether all customer-program shortfalls are systematically reconciled against dedicated investment, mitigation, prior recovery and notice deadlines today.

### "We use ERP/SAP/Campfire/CLM"

Position: use those systems as source/context where authorized; the wedge is the bounded evidence-first recoverability determination and assisted action package.

### "We do not know if there is a contractual right"

Position: that is acceptable for eligibility. Do not promise a right. The audit separates economic exposure from contractual/commercial support and can conclude zero/unknown.

### "Success fee only"

Do not accept automatically. Test hybrid economics only if the case is qualified, attribution can be defined and the expected recoverable cash is large enough to support delivery cost/risk.

### "Send information"

Reply with a concise one-page scope and ask one qualifying question: whether there is a current/recent program with lower-than-anchored volume plus unrecovered supplier-specific investment. Do not classify this as WTP.

## Stop / escalation conditions

Stop or escalate before positive recoverability language when:

- commitment is forecast-only/ambiguous;
- contract/amendment cannot be matched;
- notice window is unknown/expired;
- exposure is fully amortized, mitigated or already paid;
- duplicate recovery risk exists;
- legal interpretation becomes material;
- requested data would cross tenant/company boundaries without authorization.

## ACTIVE

Convert the first real UK reply into a buyer-qualified bounded case, then seek the smallest costly commitment that can honestly satisfy T3.

## NEXT

If no replies arrive after the first response window, use evidence-preserving follow-up and a second qualified UK cohort; do not declare lack of demand from silence alone.
