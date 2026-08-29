# RoyaltyRecover — Assisted Commercial Offer v0.1

Date: 2026-08-29
Status: HYPOTHESIS READY FOR PILOT DESIGN, NOT YET MARKET-VALIDATED

## Entry offer

### Royalty Recoverability Scan

Question answered:

**Which licensees are worth deeper investigation now, what is actually supported by the contract/data, and which audit/lookback windows require attention?**

This is deliberately not sold as a formal contractual audit and not as "AI found money."

### Minimum client inputs

Required for a calculable case:
- operative license agreement;
- amendments / side letters known to affect economics;
- royalty statements for tested periods;
- payment history / payment evidence;
- available sales, usage or transaction exports needed for the tested royalty base.

If any required source is unavailable, the output records the gap rather than inventing a value.

## Deliverables

Per agreement/licensee:
1. operative-version status;
2. sourced royalty rule(s);
3. sourced audit-right/lookback/notice fields where present;
4. expected-vs-reported-vs-paid deterministic reconciliation where possible;
5. supported variance, or UNKNOWN / NEEDS_DATA / PROFESSIONAL_REVIEW / NO_DEFENSIBLE_RECOVERY;
6. missing-evidence request;
7. deadline state;
8. evidence-readiness score / triage priority;
9. formal-auditor requirement if the contract states one;
10. recommended next operational step, subject to human review.

Portfolio output:
- ranked recoverability register;
- evidence completeness register;
- closing-window queue;
- no-recovery list (important for avoiding wasteful audits);
- recommended formal-audit shortlist.

## Escalation offer

### Audit Preparation & Recovery Support

Where a case survives the scan:
- normalize transaction schedules;
- prepare calculation schedules;
- produce sourced questions and data requests;
- prepare auditor/counsel evidence packet;
- track audit findings, responses, settlement and payment evidence;
- independently record verified incremental recovery.

When the agreement requires an independent CPA/qualified auditor, the formal audit is performed by the qualified partner, not relabeled RoyaltyRecover software.

## Pricing architecture — assumptions, not validated market prices

The system must support three independent components:

1. **Scan fee** — fixed fee per portfolio / batch.
2. **Monitoring fee** — recurring subscription after a portfolio is normalized.
3. **Recovery component** — optional and jurisdiction/engagement-specific only after legal/professional validation.

Current proposed test cells:
- Starter recoverability scan: EUR 1,500–3,000 for a small bounded portfolio.
- Portfolio scan: EUR 5,000–12,000 where contract/data volume supports the economics.
- Monitoring: EUR 500–2,500/month depending on active agreements/reporting volume.
- Success component: test 10–20% of *verified incremental recovery attributable to the engagement*, never money demonstrably due/paid without RoyaltyRecover.

These numbers are price experiments, not statements of industry-standard pricing. Published competitor evidence currently validates fixed-fee, percentage-of-findings and contingent pricing structures but not these exact euro bands.

## Unit-economics acceptance rule

A scan should not be sold if expected delivery cost consumes the majority of fixed fee without a credible path to either:
- formal-audit/recovery support revenue; or
- recurring monitoring revenue.

Pilot instrumentation must record:
- agreements processed;
- licensees processed;
- source rows processed;
- human review minutes;
- data-cleaning minutes;
- professional-partner cost;
- scan revenue;
- monitoring revenue;
- recovery revenue;
- verified recovered cash;
- time to first defensible finding;
- false-positive rate;
- no-recovery rate.

## Commercial truth policy

Never promise a recovery rate or money amount before source-supported analysis.

Allowed promise:
**"We will independently test what your agreements, statements, payments and available source data support, show the calculation, and tell you where the evidence does not support a recovery claim."**

Disallowed promise:
**"We recover 10% of your royalties"** or any equivalent unsupported outcome guarantee.

## Pilot-ready sales gate

The offer becomes sellable as an assisted pilot before full SaaS automation when RoyaltyRecover can reproducibly execute:

agreement + amendments -> sourced rules -> statements/payments/data -> deterministic reconciliation -> fail-closed finding -> deadline/audit-right triage -> human review -> evidence packet -> partner route where needed -> outcome ledger.

Real formal recovery remains an external commercial proof gate; synthetic evidence cannot substitute for money actually recovered.
