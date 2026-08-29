# EarnedCash — T1 BATON — 2026-08-29

## STATE

`T1_PILOT_CAPABLE_ASSISTED_LOCAL / MARKET_NOT_EXPOSED / REAL_CUSTOMERS_0 / VERIFIED_REAL_CASH_0 / REVENUE_0`

This terminal applies to the isolated successor branch only. It is not a production, market-validation, pilot-validation or commercial-readiness claim.

## EXACT SOURCE / VERIFICATION

- Base lane: `earnedcash/factory-v0`
- Base HEAD repaired from: `ecc58ab65b5e1addffa8e98d9686d78c20ab42ea`
- Successor: `earnedcash/dashboard-mobile-green-repair-20260829`
- Verified pre-BATON HEAD: `8bae7fd26ec93141c4bec10cc404d4ad7eb730f4`
- DRAFT PR: `#792`
- ObraSignal Quality run: `33269593971` / #3726 — SUCCESS
- Python: `891 passed, 2 skipped`
- Mobile: Expo Doctor SUCCESS, critical-detail smoke SUCCESS, Expo web export SUCCESS.

## T1 GATE EVIDENCE

- Tenant-scoped company/customer/project/contract/case persistence is implemented and covered by the repository test suite.
- Project reconciliation, recovery queue persistence and tamper-evident audit history are implemented.
- `AssistedPilotOperator` derives due truth from explicit independently reviewed due-date evidence instead of client-provided `due=true` self-attestation.
- Case progression is fail-closed: customer approval is required for action approval/request; settlement evidence is required for SETTLED; exact-scope independently verified bank-receipt evidence is required for PAID.
- `CashEvidence` requires tenant/project/currency/amount exact match and independent verification; credit notes cannot self-certify as cash.
- Synthetic pilot E2E proves: evidence reconciliation -> queue -> customer-approved action -> recovery request -> exact bank evidence -> PAID -> verified cash -> attribution -> fee -> backup -> verified restore.
- Synthetic zero-recovery path correctly produces no queue, no verified cash and zero fee.
- Diversified assisted-pilot matrix checks five distinct synthetic companies against independent exposure oracles; unknown due evidence remains UNKNOWN and creates no recovery queue.
- Backup/restore integrity is exercised by the E2E pilot and dedicated backup tests.
- Dashboard template resolution and Expo SDK patch mismatch were repaired in #792.

## PRODUCT TRUTH

Current product can support a bounded assisted Historical Closeout Cash Audit with local/pilot persistence and human review. It may prepare evidence-supported recovery candidates and a customer-approved action queue. It cannot assert legal entitlement, automate debtor contact, infer missing due dates, count a ledger payment as verified cash, or mark a case PAID without independent exact-scope bank evidence.

## BUSINESS TRUTH

- Wedge: `HISTORICAL_CLOSEOUT_CASH_AUDIT`
- Initial ICP remains UK specialist contractors/subcontractors with document-rich completed/late-stage project books.
- Real customer data: none.
- Real market exposure from this lane: none evidenced.
- Real pilot: none.
- Real verified recovery: 0.
- Platform revenue: 0.
- Pricing remains a test hypothesis; no WTP proof.

## ACTIVE

Prepare safe T2 market-exposure assets and a real-pilot evidence gate without sending external communication.

## NEXT

1. Freeze narrow qualification criteria for a first historical closeout scan.
2. Freeze real-pilot acceptance/evidence boundaries and legal/regulatory referral boundary.
3. Prepare a reversible market-exposure/operator pack with no named prospect.
4. Only after authorized exposure: record named prospect, exact offer, timestamp, transmission evidence and response truth.

## WAIT / EXTERNAL

- Real customer/prospect exposure and contact.
- Real customer historical project records.
- Jurisdiction-specific review before EarnedCash itself performs regulated/legal collection activity or debtor contact.
- Production deployment, secrets, real billing/payment authority.

## RESUME_AT

Complete T2 preparation artifacts on this isolated lane; then move to the next portfolio Factory if the remaining transition requires external authority.