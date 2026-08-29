# EarnedCash — Forensic Validation & Pilot Wedge

**State:** NARROW → PROMOTE PILOT BUILD  
**Date:** 2026-08-29  
**Launch market:** United Kingdom first  
**Repository lane:** `earnedcash/factory-v0`  
**Base main:** `66d43f6fd51cf9cea08016dad335aaa04b711a24`  
**Draft PR:** `#719`

## Decision

The broad problem is real, but a generic retention tracker, pay-application tracker or debt-collection product is not differentiated enough.

Freeze the initial wedge as:

> **Historical Closeout Cash Audit**
>
> Import 2–5 years of completed / late-stage projects and reconcile documentary evidence across certification, invoicing, payment, retention and agreed final accounts to identify evidence-supported value that should be reviewed for conversion to cash.

The product must never represent potential, disputed, not-yet-due, unsupported or mixed-currency value as verified recovery.

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
- FCA / legal perimeter for any activity that crosses from analytics/evidence preparation into third-party debt collection, claims management, legal advice or litigation. Initial product design keeps debtor contact and legal escalation customer-controlled or partner-controlled pending jurisdiction-specific review.

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
5. documentary payment / credit / deduction mismatches
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
- success fee only on independently verified cash/credit actually received and attributed to the EarnedCash action.

**Pricing test:** benchmark around the market-proven 15% success-fee reference; test lower/hybrid variants rather than declaring a final price before real delivery economics exist.

## Minimum operation

`company → customer → project → contract → import → certification → invoice → payment → retention/final account → evidence lineage → reconciliation → human review → recovery queue → customer-approved action → recovery tracking → exact-scope payment evidence → verified cash → attribution → fee`

No collection promise. No “AI recovered £X” claim. `UNKNOWN` remains `UNKNOWN`.

## Product architecture

EarnedCash remains an independent specialist workflow. Reuse only stable infrastructure patterns/capabilities such as identity, organizations, evidence/provenance, permissions, events, audit and configuration. Keep EarnedCash business logic and customer data private to its capability/runtime.

No production database, deployment, secrets, billing or main-branch wiring has been changed by this lane.

## Current executable proof

Implemented on the isolated branch:
- project-level evidence-gated reconciliation;
- transaction-level `APPLICATION → CERTIFICATE → INVOICE → PAYMENT/CREDIT/DEDUCTION` matching;
- tenant-scoped CSV import;
- fail-closed multi-tenant and mixed-currency detection;
- independent synthetic portfolio with six diversified companies;
- independent oracle / zero-recovery cases;
- retention maturity engine with defects / closeout / release-evidence gates;
- final-account engine separating contractor position, customer position and agreed value;
- evidence-only recovery queue;
- tamper-evident audit chain;
- tenant-safe SQLite pilot persistence for company/customer/project/contract/cases/verified cash/audit;
- pure service contract plus Flask adapter;
- persistent pilot API for entity creation, project reconciliation, queue persistence, case reads and audit reads;
- stale safe-queue clearing when new evidence becomes UNKNOWN;
- evidence-gated case transition state machine;
- verified-result fee calculation with attribution gate;
- exact-scope cash-evidence verifier requiring tenant/project/currency/amount match.

### Red-team repairs already made

1. **P0 — false verified cash:** initial `paid_value` could be exposed as verified cash without payment evidence. Repaired; exact verified payment evidence is now required.
2. **Regression — test environment leakage:** Flask test mutated global auth environment and contaminated unrelated ObraSignal tests. Repaired with pytest `monkeypatch`; subsequent Python CI passed.
3. **P0 — cross-tenant lineage:** cross-tenant references are explicit P0 and fail closed.
4. **P0 — independent multi-tenant aggregation:** a result cannot aggregate multiple tenants.
5. **P1 — mixed-currency aggregation:** GBP/EUR/etc. cannot be summed without an explicit FX model; mixed datasets fail closed.
6. **P1 — stale recovery queue:** if new evidence becomes UNKNOWN, prior queue items are cleared rather than silently retained.

## Verification truth

- On exact head `833567f095068278e22f0ad0d33a4e1b93c369a0`, GitHub Actions Python job passed the entire repository suite: **805 passed, 2 skipped**.
- The same workflow's mobile job failed because the unchanged base mobile dependency has `react-native 0.86.2` while `expo-doctor` expects `0.86.3`. EarnedCash changed no mobile files.
- Later EarnedCash commits add the case workflow, fee model and cash-evidence verifier. Therefore the **current branch head is NOT_FULLY_VERIFIED until exact-head CI completes**.
- The connector blocked creation of the full cash-verifier test file; that verifier remains specifically `TEST_WRITE_BLOCKED / NOT_FULLY_VERIFIED` even though the module is committed.

## Scoreboard

- `CURRENT_TERMINAL = T0 — THESIS SURVIVED (NARROWED); PILOT BUILD ADVANCED`
- `NEXT_TERMINAL = T1 — PILOT CAPABLE`
- `CURRENT_WEDGE = HISTORICAL_CLOSEOUT_CASH_AUDIT`
- `ONE_CURRENT_BOTTLENECK = exact-head verification + complete evidence-to-cash/action persistence`
- `THESIS_STATE = PROMOTE_PILOT_BUILD`
- `DISTINCTNESS_STATE = INDEPENDENT_SPECIALIST + SHARED_INFRA_PATTERNS`
- `ICP_STATE = CANDIDATE; REAL-DATA VALIDATION REQUIRED`
- `BUYER_STATE = CFO/FD/COMMERCIAL DIRECTOR CANDIDATE`
- `TRIGGER_STATE = OLD OPEN PROJECTS / CLOSEOUT / RETENTION / CERTIFIED CASH`
- `MATERIALITY_STATE = PROVEN INDUSTRY-WIDE; CUSTOMER-LEVEL UNKNOWN`
- `COMPETITION_STATE = STRONG; GENERIC TRACKING REJECTED`
- `WTP_STATE = SUCCESS-FEE MARKET SIGNAL PROVEN; EARNEDCASH PRICE UNKNOWN`
- `RETENTION_ENGINE = IMPLEMENTED / TESTED`
- `FINAL_ACCOUNT_ENGINE = IMPLEMENTED / TESTED`
- `PAYMENT_RECONCILIATION = IMPLEMENTED / TRANSACTION-LINEAGE TESTED`
- `BLOCKER_ENGINE = PARTIAL / EMBEDDED; standalone classification expansion pending`
- `RECOVERY_ENGINE = EVIDENCE-ONLY QUEUE IMPLEMENTED`
- `EVIDENCE_ENGINE = LINEAGE + CASH EXACT-MATCH VERIFIER; verifier exact tests pending`
- `ORACLE_STATE = IMPLEMENTED CORE`
- `SYNTHETIC_STATE = SIX DIVERSIFIED COMPANIES`
- `ZERO_RECOVERY_STATE = PASS`
- `RED_TEAM_STATE = ACTIVE`
- `P0 = 0 KNOWN UNREPAIRED IN LAST VERIFIED HEAD; CURRENT HEAD NOT_FULLY_VERIFIED`
- `P1 = further date-boundary, duplicate-evidence, customer/company referential and action-persistence hardening required`
- `O BRASIGNAL_RELATIONSHIP = INDEPENDENT SPECIALIST; no merge evidence`
- `SCOPELEDGER_RELATIONSHIP = REFERRAL FOR UNRESOLVED CHANGE/TIME/LD`
- `INDUSTRIAL_CLAIMS_RELATIONSHIP = REFERRAL FOR COMPLEX HIGH-VALUE DISPUTE`
- `OFFER_STATE = V0 FROZEN`
- `APP_STATE = ISOLATED PERSISTENT PILOT API; NOT PRODUCTION WIRED`
- `PILOT_STATE = NOT T1 YET`
- `MARKET_STATE = VALIDATED PROBLEM/COMPETITION SIGNALS; NO REAL CUSTOMER EXPOSURE`
- `REAL_CUSTOMERS = 0`
- `IDENTIFIED_VALUE = £0 VERIFIED`
- `VERIFIED_CASH = £0`
- `REVENUE_RECEIVED = £0`
- `ACTIVE = exact-head CI + cash verifier tests/integration + case-action persistence hardening`
- `NEXT = executive report + broader mandatory red-team matrix + assisted-pilot operating pack`
- `WAIT = real customer data; jurisdiction-specific legal/regulatory review before third-party collection activity`
- `BLOCKER = mobile quality job baseline mismatch; cash-verifier test write blocked by connector; neither blocks other safe EarnedCash work`
- `RESUME_AT = verify current head; repair any EarnedCash failure first; then integrate verified cash evidence into persisted case transitions without client self-attestation`

## Evidence references

- UK Parliament, Commercial Payments Bill [HL], current bill/stage pages (2026).
- House of Lords Hansard, 9 June 2026, Commercial Payments Bill [HL].
- GOV.UK, Commercial Payments Bill overview and late-payment reforms (2026).
- GOV.UK / HMRC Business Income Manual BIM51520, updated 4 August 2026.
- Hay's Collections, Construction Retention Recovery.
- OwePath, construction commercial control product.
- Siteline, construction billing software for subcontractors.

These references validate market/problem/competition signals. They do not prove any EarnedCash customer recovery or revenue.
