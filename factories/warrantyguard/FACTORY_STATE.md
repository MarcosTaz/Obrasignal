# WARRANTYGUARD — Factory State / BATON

## MISSION
Finish WarrantyGuard as a real, tested, reliable, pilot-capable, commercial-capable, supportable operational company + product. Current wedge remains supplier-side automotive pre-acceptance control for inbound OEM/customer warranty/quality debits. Preserve zero-false-warranty, zero-invented-rights, zero-unsupported-calculations and zero-fake-validation.

## MODE
`A / MAXIMUM SAFE AUTONOMY / CONTINUOUS EXECUTION / REPOSITORY-FIRST / EVIDENCE-FIRST / FAIL-CLOSED / NO-AUTOMATIC-MERGE / NO-STOP-BETWEEN-SAFE-TASKS`

Error/blocker/task-end/technical-window-end != Factory stop. PROJECT COMPLETE may be declared only after all applicable completion gates are evidenced.

## CLASSIFICATION
`NARROW → PROCEED`

## REPOSITORY
Repository: `MarcosTaz/Obrasignal`
Branch: `factory/warrantyguard-debitproof-v084`
PR: `#805` draft / no automatic merge

## VERSION / SOURCE TRUTH
VERSION = `0.8.5`
RUNTIME = `Node.js >=20 / zero external npm dependencies`
ARTIFACT_SHA256 = `1a2beb994aae62c582272e73ceb89418898f047dc6b218264889219c3fd2f240`
LIBRARY = `/WarrantyGuard/warrantyguard-prototype-v0.8.5.tar.gz`
PRE_SYNC_TEST_STATE = `52/52 PASS`
PRE_SYNC_REDTEAM = `10,000 debit cases: 8,829 known + 1,171 UNKNOWN; 1,000 recovery cases PASS`
PRE_SYNC_ORACLE = `18/18 PASS`
PRE_SYNC_CLEAN_EXTRACTION = `PASS`
REPOSITORY_CI = `REVERIFY_REQUIRED_AFTER_v0.8.5_SYNC`

## CURRENT WEDGE
`Pre-acceptance financial control for recurring inbound OEM/customer warranty and quality debits.`

Current structured flow:
INCOMING DEBIT → tenant import → mapping → approved contract/version/source lineage → evidence claims/reviewer lineage → warranty/cost eligibility → root-cause/responsibility → duplicate/prior-credit/payment → SUPPORTED/PARTIALLY_SUPPORTED/DISPUTABLE/UNKNOWN → draft-only dossier → verified outcome reconciliation.

Truth invariants:
- DEBIT != LIABILITY.
- Missing mapping/contract/evidence/root-cause/responsibility => UNKNOWN.
- UNKNOWN exposes no supported/disputable money.
- NFF requires explicit contractual rule.
- Duplicate/prior-credit/mapping/warranty/cost challenges require evidence provenance when external context is used.
- Potential duplicate never auto-rejects.
- Prior payment != prior credit.
- Credit and cash are not double-counted by default.
- Draft dispute != submitted dispute != approved credit != received credit/cash.

## PRODUCT BOUNDARY
`ASSISTED_LOCAL / NO SHARED CUSTOMER PERSISTENCE / HUMAN_REVIEW_REQUIRED`

Implemented: strict CSV import; tenant checks; 500-row/2MB pilot bounds; ISO dates/currency; contract version selection; contract/rules/source hashes; approval lineage; evidence hashes/claims/reviewer lineage; conservative responsibility/warranty/cost logic; duplicate handling; prior credit/payment separation; currency-separated summaries; UNKNOWN money suppression; draft dispute packs; recovery state machine; token-protected localhost operator API; CLI; synthetic oracle; deterministic red-team; pseudonymization helper.

Public/multi-user deployment remains blocked pending AuthN/AuthZ, secure persistence/secrets, audit logs, backup/restore, deletion, monitoring, rollback and independent cross-tenant security proof.

## PERMANENT COMPLETION GATES
A DOCUMENTS = `PARTIAL` — structured inputs work; source warranty/contract document ingestion still incomplete.
B EXTRACTION = `NOT_PROVEN` — clause/date/party/condition extraction from source documents not yet end-to-end.
C WARRANTY LOGIC = `PARTIAL` — structured approved rules conservative; free-document coverage/exclusion/deadline logic incomplete.
D EVIDENCE = `PARTIAL/PASS_FOR_STRUCTURED_WEDGE`.
E FALSE-CLAIM CONTROL = `STRONG_FOR_STRUCTURED_WEDGE / CONTINUE_REDTEAM`.
F CALCULATIONS = `PASS_FOR_CURRENT_WEDGE`.
G CASE = `PASS_SYNTHETIC_STRUCTURED / NOT_REAL_CASE_VALIDATED`.
H PRODUCT = `PARTIAL_ASSISTED_LOCAL`.
I SECURITY = `PASS_WITHIN_LOCAL_NO-PERSISTENCE_BOUNDARY / PUBLIC_SECURITY_NOT_PROVEN`.
J BILLING = `NOT_IMPLEMENTED/NOT_PROVEN`.
K SUPPORT = `PARTIAL_DOCUMENTED / NOT_EXERCISED`.
L OPERATIONS = `PARTIAL_LOCAL / PUBLIC_MONITORING_NOT_PROVEN`.
M PILOT = `PILOT_CAPABLE_ASSISTED_LOCAL / NO REAL PILOT YET`.
N VALUE = `NOT_PROVEN_REAL`.
O COMMERCIAL = `NOT_PROVEN`.
P RETENTION = `NOT_PROVEN`.
Q ECONOMICS = `PRICING_HYPOTHESES_ONLY`.
R QUALITY = `NO KNOWN P0 IN LOCAL BOUNDARY; REPOSITORY CI REVERIFY ACTIVE`.
PROJECT_COMPLETE = `NO`.

## REAL EXPOSURE / BUSINESS TRUTH
T1 = `PASSED — ASSISTED_LOCAL`
CURRENT_TERMINAL = `T2 — MARKET EXPOSED`
NEXT_TERMINAL = `T3 — COMMERCIAL PROOF`
REAL_CUSTOMERS = `0`
PAID_PILOTS = `0`
REAL_DISPUTABLE_VALUE = `€0`
VERIFIED_RECOVERY_REAL = `€0`
REVENUE_RECEIVED = `€0`
WTP = `UNPROVEN`

1. AFIA → `info@afia.pt` → Gmail `1a04dd405f82f212` → SENT
2. Simoldes → `alexandre.batista@simoldes.com` → Gmail `1a04dd750c85a135` → SENT
3. FEHST → `fehst.comp@fehstgroup.com` → Gmail `1a04df7aca576132` → SENT
4. PLASTIFA → `plastifa@plastifa.pt` → Gmail `1a04df81b959496f` → SENT

Silence is `NO_REPLY_YET`, never rejection or demand proof.

## DONE
- v0.8.5 evidence hardening: explicit NFF rule; evidence-backed duplicate/prior-credit/mapping/warranty/cost; typed rules/timestamps.
- artifact/package clean-extraction proof persisted in Library.
- repository branch and draft PR #805 established.
- isolated WarrantyGuard GitHub workflow established.
- verifier + HTTP smoke synchronized to v0.8.5 after CI exposed version drift.

## IN_PROGRESS
1. repository CI re-verification of synchronized v0.8.5;
2. Tier-0 document ingestion/extraction and deadline/condition truth;
3. complete case dossier from source-document lineage;
4. support/incident/billing/customer-journey gates around assisted operation.

## ACTIVE
`DOCUMENT_TRUTH + REPOSITORY_CI_REPAIR`

## NEXT
1. make WarrantyGuard workflow GREEN on exact current HEAD;
2. add conservative source-document ingestion and clause/date/party/condition extraction;
3. add explicit deadline/exclusion/condition UNKNOWN rules and adversarial tests;
4. connect extracted terms to case dossier with source/clause hash lineage;
5. test representative document cases end-to-end;
6. strengthen customer journey/support/operations and safe billing sandbox;
7. continue GTM/response qualification in parallel without inventing WTP;
8. never promote PILOT_VALIDATED/MARKET_VALIDATED/COMMERCIAL_READY without real evidence.

## WAIT / OWNER-ONLY DEPENDENCIES
- T3 and gates N/O/P require real external customer behavior.
- Public deployment credentials/security architecture, legal signatures, banking/KYC and binding commercial acceptance remain owner/external dependencies when reached.
- These do not block safe product/repository work.

## TEST_STATE
Current pre-sync source proof: `52/52 + redteam + oracle + clean extraction PASS`.
Repository HEAD proof: `ACTIVE / must pass after sync and subsequent document-truth changes`.

## REGRESSIONS
- v0.8.5 repository sync initially left verifier/http smoke pinned to v0.8.4; GitHub workflow correctly failed. Root cause identified and repaired; exact-head re-test pending.

## SECURITY_STATE
`ASSISTED_LOCAL_BOUNDARY_GREEN / PUBLIC_MULTIUSER_RED-BLOCKED-BY-DESIGN`

## UNRESOLVED_ASSUMPTIONS
- customer data/document formats and real warranty/CSR variation not yet observed;
- WTP and actual cost-to-serve unknown;
- working commercial name DebitProof not formally cleared;
- real pilot document/legal/data-handling constraints unknown until qualified customer exists.

## RESUME_AT
`EXACT_HEAD_CI → DOCUMENT_INGESTION → EXTRACTION/DEADLINE_LOGIC → DOCUMENT_CASE_DOSSIER → ADVERSARIAL_CASES → CUSTOMER_E2E → SECURITY/BILLING/SUPPORT/OPS → REAL_RESPONSE/PILOT → VALUE/PAYMENT/RETENTION → ALL_COMPLETION_GATES`
