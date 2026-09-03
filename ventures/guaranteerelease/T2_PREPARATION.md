# GuaranteeRelease — T2 Market Exposure & Real-Pilot Preparation

Status: `T1_PILOT_CAPABLE_ASSISTED_LOCAL / T2_PREPARED_NOT_EXPOSED`.

This document prepares reversible commercial execution. It does not authorize external contact and does not prove demand, willingness to pay, a real release or revenue.

## 1. Narrow first-pilot ICP

Prioritize a construction/EPC/infrastructure contractor with a bounded portfolio of bank guarantees, surety bonds or related security instruments when:

- instruments can be identified individually with issuer, beneficiary, amount, currency and expiry/baseline evidence;
- the governing contract/project can be linked to each instrument;
- at least one reduction/release mechanism can be tested from documentary milestones, repayment/progress or expiry terms;
- a treasury/commercial/project reviewer can validate context and evidence;
- the customer can share a bounded evidence population without granting broad write access to bank/TMS/ERP systems;
- the engagement can stop at analysis/evidence preparation without unauthorized bank, surety or beneficiary communication.

Initial instrument priority:

1. advance-payment guarantees with progressive reduction language;
2. performance guarantees with milestone/completion reduction or release conditions;
3. retention/warranty/defects instruments where release conditions are documentable.

Hold as `NOT_QUALIFIED` or `EVIDENCE_REQUIRED` when instrument identity, contract linkage, baseline terms, source evidence or reviewer access are absent; when the case depends principally on a legal dispute; or when value requires assuming that expiry/cancellation automatically equals collateral/capacity release.

## 2. Qualification score

UNKNOWN scores zero.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Instrument identity | absent | partial | complete/consistent |
| Contract/project linkage | absent | indirect | explicit |
| Reviewed baseline evidence | unavailable | partial | available |
| Reduction/release basis | narrative | plausible | explicit documentary basis |
| Progress/repayment/milestone evidence | absent | partial | source evidence available |
| Reviewer access | absent | unconfirmed | named internal reviewer role |
| Portfolio boundary | unbounded | partially bounded | pilot population defined |
| Outcome-verification path | none | manual/unconfirmed | bank/surety/collateral evidence path identified |

- `0–6`: `NOT_QUALIFIED`
- `7–11`: `EVIDENCE_REQUIRED`
- `12–16`: `ASSISTED_PILOT_CANDIDATE`

This is an admissibility score, never proof of entitlement or release.

## 3. External-state evidence gates

### T2_MARKET_EXPOSED

Requires durable evidence of:

1. named real prospect/company;
2. exposure timestamp;
3. exact offer/version;
4. channel;
5. proof of actual transmission/publication.

Transmission proves exposure only.

### REAL_PILOT_CANDIDATE

Requires:

- real portfolio/problem evidence;
- at least one real instrument/document class available or explicitly committed for review;
- customer-side reviewer/contact;
- authorization boundary for document review;
- qualification result `ASSISTED_PILOT_CANDIDATE`;
- bounded scope and commercial basis;
- no unresolved legal/regulatory/communication blocker preventing analytical work.

### PILOT_ACCEPTED

Requires explicit customer acceptance of scope, fee basis, evidence boundary, reviewer/owner and start condition.

### PILOT_STARTED

Requires authorized customer evidence received and at least one real instrument admitted to the reviewed-evidence workflow. Real customer documents must not be committed to public/synthetic repository artifacts.

## 4. Outcome truth ladder

Do not collapse these states:

- `POTENTIAL_RELEASE`: calculation/evidence candidate only;
- `EVIDENCE_SUPPORTED_REDUCTION_OR_RELEASE`: reviewed evidence supports a bounded commercial position;
- `CUSTOMER_APPROVED_ACTION`: customer chooses/approves an action;
- `ISSUER_OR_BENEFICIARY_CONFIRMED`: external party evidence confirms cancellation/reduction/release status;
- `COLLATERAL_RELEASED`: separate durable evidence confirms collateral release;
- `CAPACITY_RESTORED`: separate evidence supports restored bonding/bank capacity;
- `VERIFIED_CUSTOMER_VALUE`: value supported by the appropriate downstream outcome evidence;
- `FEE_DUE`: commercial agreement plus verified value supports the platform fee;
- `PLATFORM_REVENUE_PAID`: separate settlement evidence proves our fee was actually paid.

Expiry alone, instrument cancellation alone, or a candidate reduction does not prove collateral/capacity value.

## 5. Initial offer

Working offer: `Security Release & Capacity Recovery Scan — Assisted Pilot`.

Bounded promise:

- reconcile a small portfolio of guarantees/security instruments to governing project/contract evidence;
- identify document-supported reduction/release candidates and missing evidence;
- maintain reviewer separation and audit lineage;
- track downstream cancellation, collateral and capacity outcomes separately;
- measure delivery effort and observed value.

Explicit non-promises:

- guaranteed release;
- legal advice/representation;
- automatic bank/surety/beneficiary contact;
- automatic cancellation instruction;
- replacement of TMS/ERP/bank portal;
- unsupported portfolio-wide release percentage.

## 6. Reversible exposure message skeleton

`We run a bounded independent review of construction/EPC guarantee portfolios to identify instrument reductions or releases that are supported by the governing contract and project evidence but may not yet be reflected operationally. The first pilot is evidence-first: one small instrument population, no write access to bank/TMS systems, no automatic bank or beneficiary contact, and any missing or conflicting fact remains UNKNOWN.`

`The output separates a potential reduction/release from issuer confirmation, collateral release and restored capacity, so those outcomes are not counted before evidence exists.`

Preparation copy only; not authorized for external transmission by this file.

## 7. Prospect record

- Prospect ID: `UNASSIGNED`
- Company: `UNASSIGNED`
- Country: `UNASSIGNED`
- Contact role: `UNASSIGNED`
- Instrument portfolio hypothesis: `UNASSIGNED`
- Evidence source: `UNASSIGNED`
- Exposure timestamp: `UNASSIGNED`
- Channel: `UNASSIGNED`
- Exact offer version: `UNASSIGNED`
- Transmission evidence: `UNASSIGNED`
- Response: `UNKNOWN`
- Qualified problem: `UNKNOWN`
- Evidence availability: `UNKNOWN`
- Reviewer access: `UNKNOWN`
- Authorization: `UNKNOWN`
- Commercial state: `NOT_EXPOSED`

## 8. Production dependencies kept separate from T2

Before a production/customer-data deployment, independently close:

- production IAM/SSO/MFA;
- immutable production document-ingestion/content hashing;
- secrets/config management;
- monitoring/backup/restore operationalization;
- jurisdiction/customer data/privacy terms;
- bank/surety/beneficiary communication authority;
- billing/revenue reconciliation.

These dependencies do not justify falsely calling preparation `MARKET_EXPOSED`, but they also should not be hidden by a T1 label.
