# EarnedCash — Forensic Validation & Pilot Wedge

**State:** NARROW → PROMOTE PILOT  
**Date:** 2026-08-29  
**Launch market:** United Kingdom first  
**Repository lane:** `earnedcash/factory-v0`  
**Base main:** `66d43f6fd51cf9cea08016dad335aaa04b711a24`

## Decision

The broad problem is real, but a generic retention tracker, pay-application tracker or debt-collection product is not differentiated enough.

Freeze the initial wedge as:

> **Historical Closeout Cash Audit**
>
> Import 2–5 years of completed / late-stage projects and reconcile documentary evidence across certification, invoicing, payment, retention and agreed final accounts to identify evidence-supported value that should be reviewed for conversion to cash.

The product must never represent potential, disputed, not-yet-due or unsupported value as verified recovery.

## Why the thesis survives

### PROVEN

- Construction retentions represent material working capital. During the 9 June 2026 Lords debate on the Commercial Payments Bill, the government cited Construction Leadership Council estimates of approximately **£4bn–£6bn held** across the UK industry at any time and approximately **£223m lost annually through insolvency**.
- The Commercial Payments Bill is active legislation, not enacted law. It would prohibit retention deductions/withholding and introduce a transition. This strengthens the pain signal but also means a retention-only company has shrinking long-term UK scope.
- Current purpose-built software already tracks pay applications, certification, retainage/retention, A/R, overdue invoices, defects and chase queues. Therefore “better tracking” alone is not a sufficient wedge.
- Construction-specific recovery firms already offer no-upfront / success-fee retention recovery. Hay's Collections advertises 15% commission on recovered retention. Therefore success-fee economics are market-proven in principle, but direct debt recovery is competitive and may introduce regulatory/legal perimeter issues.

### SIGNAL

- HMRC guidance updated 4 August 2026 notes that construction retentions can be held over maintenance periods and that customers may be reluctant to pay retention monies, sometimes resulting in non-payment.
- The UK legislative direction increases urgency for historical-book cleanup during the transition period.
- Software vendors market integrations with accounting/project systems and automated imports, indicating that the required data often exists in digital exports even where it is fragmented.

### ASSUMPTION TO TEST WITH REAL DATA

- A 2–5 year historical scan can find enough incremental, evidence-supported cash per customer to support a success fee after delivery cost.
- Specialist subcontractors with multiple concurrent/completed projects have the best ratio of recoverable value to data complexity.
- CFO / Finance Director / Commercial Director owns budget; QS / Commercial Manager / A/R supplies evidence and operates the queue.
- Continuous monitoring after the historical audit can support recurring subscription revenue.

### UNKNOWN / REQUIRES_REVIEW

- Exact recoverable percentage of a typical contractor's historical open balance.
- Exact WTP and optimal fee by ICP.
- FCA / legal perimeter for any activity that crosses from analytics/evidence preparation into third-party debt collection, claims management, legal advice or litigation. Initial product design therefore keeps debtor contact and legal escalation customer-controlled or partner-controlled pending jurisdiction-specific review.

## Initial ICP

Prioritize UK specialist contractors and subcontractors with:
- material multi-project commercial operations;
- repeat progress applications / certification;
- historical retention/final-account exposure;
- finance + commercial records available as exports or documents.

Candidate trades: MEP, electrical, HVAC, interiors/drywall, facade, steel, fire protection, civils, groundwork, roofing and fit-out.

Do not set a hard turnover floor until real scan economics are measured.

## In-scope launch categories

1. `RETENTION_MATURED_UNRELEASED`
2. `CERTIFIED_NOT_INVOICED`
3. `INVOICED_DUE_UNPAID`
4. `FINAL_ACCOUNT_AGREED_UNPAID`
5. documentary payment / deduction mismatches once matching engine is added
6. explicit `NOT_YET_DUE`, `DISPUTED`, `UNKNOWN`, `REQUIRES_REVIEW`

## Explicit exclusions

- unresolved variation entitlement;
- extension-of-time / delay entitlement;
- LD defence;
- complex claims;
- generic debt collection;
- lending, factoring, debt purchase or balance-sheet finance.

Unresolved change/time entitlement routes to ScopeLedger. High-value complex disputes route to Industrial Claims.

## Commercial offer v0

**Historical Closeout Cash Scan**
- zero-upfront intake;
- customer supplies 2–5 years of project/payment records;
- deterministic reconciliation + evidence review;
- queue split into evidence-supported, not-yet-due, disputed and unknown;
- customer approves every external action;
- success fee only on independently verified cash/credit actually received.

**Pricing test:** benchmark around the market-proven 15% success-fee reference; test lower/hybrid variants rather than declaring a final price before real delivery economics exist.

## Minimum operation

`contract/project export → certification → invoice → payment → retention/final account → evidence lineage → reconciliation → human review → recovery queue → customer-approved action → payment evidence → verified cash → fee`

No collection promise. No “AI recovered £X” claim. `UNKNOWN` remains `UNKNOWN`.

## Product architecture

EarnedCash remains an independent specialist workflow. Reuse only stable infrastructure patterns/capabilities such as identity, organizations, evidence/provenance, permissions, events, audit and configuration. Keep EarnedCash business logic and customer data private to its capability/runtime.

## Current executable proof

The first deterministic reconciliation engine now covers:
- zero-recovery / not-yet-due pass;
- matured retention with and without verified release evidence;
- certified-not-invoiced with and without certificate evidence;
- due unpaid invoices with evidence gating;
- valid deductions and disputed-value netting;
- invalid negative values;
- inconsistent cash-chain fail-closed behavior;
- final-account double-count prevention;
- tenant identity preservation.

Local verification: **12 passed**.

## Scoreboard

- `CURRENT_TERMINAL = T0 — THESIS SURVIVED (NARROWED)`
- `NEXT_TERMINAL = T1 — PILOT CAPABLE`
- `CURRENT_WEDGE = HISTORICAL_CLOSEOUT_CASH_AUDIT`
- `THESIS_STATE = PROMOTE_PILOT`
- `DISTINCTNESS_STATE = INDEPENDENT_SPECIALIST + SHARED_INFRA_PATTERNS`
- `ICP_STATE = CANDIDATE; REAL-DATA VALIDATION REQUIRED`
- `BUYER_STATE = CFO/FD/COMMERCIAL DIRECTOR CANDIDATE`
- `TRIGGER_STATE = OLD OPEN PROJECTS / CLOSEOUT / RETENTION / CERTIFIED CASH`
- `MATERIALITY_STATE = PROVEN INDUSTRY-WIDE; CUSTOMER-LEVEL UNKNOWN`
- `COMPETITION_STATE = STRONG; GENERIC TRACKING REJECTED`
- `WTP_STATE = SUCCESS-FEE SIGNAL PROVEN; EARNEDCASH PRICE UNKNOWN`
- `ORACLE_STATE = STARTED`
- `SYNTHETIC_STATE = STARTED`
- `ZERO_RECOVERY_STATE = PASS`
- `P0 = 0 KNOWN IN CURRENT ENGINE`
- `P1 = MATCHING/DATE/CURRENCY/DOCUMENT-LINEAGE EXPANSION REQUIRED`
- `REAL_CUSTOMERS = 0`
- `IDENTIFIED_VALUE = £0 VERIFIED`
- `VERIFIED_CASH = £0`
- `REVENUE_RECEIVED = £0`
- `ACTIVE = expand independent oracle + payment matching + mandatory cases`
- `NEXT = synthetic companies + import schema + evidence lineage + recovery queue`
- `WAIT = real customer data; jurisdiction-specific legal/regulatory review before external collection activity`
- `BLOCKER = none for safe product/testing work`
- `RESUME_AT = extend reconciliation from project totals to transaction-level payment/certificate/invoice matching`

## Evidence references

- UK Parliament, Commercial Payments Bill [HL], current bill/stage pages (2026).
- House of Lords Hansard, 9 June 2026, Commercial Payments Bill [HL].
- GOV.UK, Commercial Payments Bill overview and late-payment reforms (2026).
- GOV.UK / HMRC Business Income Manual BIM51520, updated 4 August 2026.
- Hay's Collections, Construction Retention Recovery.
- OwePath, construction commercial control product.
- Siteline, construction billing software for subcontractors.

These references validate market/problem/competition signals. They do not prove any EarnedCash customer recovery or revenue.
