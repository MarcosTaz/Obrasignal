# RoyaltyRecover — Formal Auditor Partner Model

Date: 2026-08-29
Status: OPERATING MODEL — PUBLIC-EVIDENCE SUPPORTED, PARTNER DEMAND NOT YET VALIDATED

## Why a partner model is necessary

RoyaltyRecover is not positioned as a substitute for a contract-required independent auditor, CPA, accountant, lawyer or other professional whose qualification is dictated by the operative agreement or jurisdiction.

Public market evidence shows that audit firms themselves may provide target selection, desk review, full audit, monitoring, negotiation and recovery support. Therefore a generic referral partnership is not automatically differentiated and can create channel conflict.

Examples reviewed include:
- 360 Royalty Audit: fixed-fee and discretionary contingent-fee structures; target selection support.
- Acumon: independent royalty/license compliance audits with fixed-fee quotations.
- Royalty Solutions Corp.: flat/fixed-fee model, explicitly not a percentage of recoveries.
- S&W Group: fixed-cost or percentage-of-findings models can exist, subject to engagement/contract terms.
- GHJ: contingent and hybrid contingent arrangements may exist but can create independence/testimony considerations.
- Stout: desk audits, field audits, monitoring and negotiation/recovery assistance.

Public sources:
- https://www.360royaltyaudit.com/fees/
- https://www.acumon.co.uk/royalty-audit
- https://royaltysolutionscorp.com/
- https://www.swgroup.com/insights-events/insights/royalty-audits-ensuring-compliance-and-maximising-revenue/
- https://www.ghjadvisors.com/ghj-insights/royalty-audits-the-benefits-of-contingency-fee-arrangements
- https://www.stout.com/en/services/regulatory-compliance/royalty-audit-services

## Initial safe commercial structure

RoyaltyRecover should begin with **separate economics** from the formal auditor:

1. Customer contracts with RoyaltyRecover for a bounded portfolio baseline / recoverability triage.
2. RoyaltyRecover identifies evidence-ready candidates, evidence gaps and no-current-recovery outcomes.
3. If a finding requires formal books-and-records access or the contract specifies an auditor qualification, RoyaltyRecover prepares a handoff packet.
4. Customer selects/contracts the auditor independently.
5. Auditor owns formal fieldwork, books-and-records access, professional conclusions, expert testimony and any audit statement within its professional remit.
6. RoyaltyRecover can ingest the resulting verified evidence and reconcile outcomes, but does not rewrite the auditor's conclusion.

## Fee rule for launch

Default initial rule:

**No percentage commission on the auditor's fee and no automatic share of formal-audit recoveries.**

Reason:
- professional-independence and contingent-fee rules vary;
- governing agreements can specify audit-cost allocation or auditor qualifications;
- some engagements can progress toward disputes/litigation where expert independence matters;
- the commercial wedge should survive on the value of portfolio screening, not depend on legally uncertain fee sharing.

Any later referral or success-linked structure is a jurisdiction- and profession-specific legal/compliance question and must be explicitly validated before use.

## Partner value proposition

RoyaltyRecover should offer an auditor leverage, not replacement:

**Inputs delivered to auditor**
- operative agreement/version identity and SHA lineage;
- reviewed source clauses and deterministic rule representation;
- royalty statements/payment/source evidence identifiers and hashes;
- period-specific deterministic calculations;
- unresolved information requests;
- audit/lookback deadline evidence where contract-supported;
- explicit reasons for escalation;
- complete audit trail of internal review decisions;
- no unsupported claim assertion.

**Work retained by auditor**
- confirmation of scope and professional qualification;
- books-and-records request/exercise of contractual access;
- testing populations and source systems not already supplied by licensor;
- accounting/professional judgment;
- formal audit findings and communications;
- testimony/dispute support when applicable.

## Handoff state machine

`PERSISTED FINDING`
→ reviewer decision `ROUTE_TO_FORMAL_AUDIT`
→ `FORMAL_AUDIT_ROUTE`
→ build immutable handoff packet
→ customer/auditor accepts externally
→ external audit evidence returns
→ outcome reconciliation
→ recovered amount remains `UNVERIFIED` until payment evidence exists.

A handoff packet does **not** mean:
- audit right definitely exists beyond evidence recorded;
- the auditor has accepted the engagement;
- money is owed;
- a claim is ready;
- recovery has occurred.

## Channel-conflict test

Gate 3 must remain OPEN until at least one of these is evidenced:
- auditor says evidence-ready candidate packs reduce scoping/data-preparation cost materially;
- TTO buyer prefers independent portfolio triage before selecting an auditor;
- fixed portfolio baseline produces candidate selection at materially lower cost than buying traditional desk audits license-by-license;
- partner is willing to receive structured handoff packets without requiring RoyaltyRecover to become a competing audit firm.

## Product consequence

Next executable product feature:

Build a tenant-scoped, immutable `FormalAuditPacket` generator that can run **only** after a reviewer has placed a `RECOVERY_CANDIDATE` into `FORMAL_AUDIT_ROUTE`. It must derive all money and lineage from persisted records, contain no user-supplied recovery amount, and always return `claim_ready=false` / `auditor_engaged=false`.
