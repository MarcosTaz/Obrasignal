# WARRANTYGUARD — Factory State / BATON

## MISSION
Finish WarrantyGuard as a real, tested, reliable, pilot-capable, commercial-capable, supportable operational company + product. Current wedge: supplier-side automotive pre-acceptance financial control for inbound OEM/customer warranty/quality debits. Preserve zero-false-warranty, zero-invented-rights, zero-unsupported-calculations and zero-fake-validation.

## MODE
`A / MAXIMUM SAFE AUTONOMY / CONTINUOUS EXECUTION / REPOSITORY-FIRST / EVIDENCE-FIRST / FAIL-CLOSED / NO-AUTOMATIC-MERGE / NO-STOP-BETWEEN-SAFE-TASKS`

Error/blocker/task-end/technical-window-end != Factory stop. PROJECT COMPLETE may be declared only after every applicable completion gate is evidenced.

## CLASSIFICATION
`NARROW → PROCEED`

## REPOSITORY
Repository: `MarcosTaz/Obrasignal`
Branch: `factory/warrantyguard-debitproof-v084`
PR: `#805` draft / no automatic merge

## VERSION / VERIFIED SOURCE TRUTH
VERSION = `0.9.0`
RUNTIME = `Node.js >=20 / zero external npm dependencies`
VERIFIED_EXECUTABLE_HEAD = `343aef3206ffdd1a0e4348e978e51d24d685cb5b`
CI_RUN = `33557506800` (`WarrantyGuard Factory`, SUCCESS)
CI_ARTIFACT_ID = `9819910373`
CI_ARTIFACT_DIGEST = `sha256:80f6556b6e23ae661706ab4a2800da8c350f4e7b1855b177bf00880fa0e45d15` (GitHub ZIP artifact digest)
SOURCE_TARBALL_SHA256 = `a7ed70cfe40f25a557473ac5f6461ee15d822234917a6b2f4c606e06d492d868`
LIBRARY = `/WarrantyGuard/warrantyguard-prototype-v0.9.0.tar.gz`
LATEST_REPOSITORY_LOGIC_HEAD_VERIFIED = `2adf69cd9077d87ebd8d0ede714c1edafb023e24`
LATEST_REPOSITORY_LOGIC_CI = `33558305997` (`WarrantyGuard Factory`, SUCCESS)

Verification on the executable source:
- `187/187` automated invariant tests PASS;
- deterministic debit red-team `10,000` cases PASS;
- recovery red-team `1,000` cases PASS;
- document adversarial matrix `16/16` PASS;
- synthetic assisted customer E2E PASS;
- assisted-local security red-team PASS;
- HTTP/operator/workspace/resource gates PASS;
- CI packaged source outside the source tree;
- CI clean-extracted the package and re-ran `npm run verify` PASS;
- downloaded CI tarball was independently SHA-checked and clean-extracted in a separate runtime; `npm run verify` again returned `187/187` and all gates PASS;
- later repository logic/compliance head `2adf69c…` independently passed the WarrantyGuard-specific workflow.

The source tar records the last independently downloaded/reverified executable artifact. Later BATON/README/compliance-only commits do not rewrite historical artifact evidence; exact-head CI remains mandatory for current repository truth.

## CURRENT WEDGE
`Pre-acceptance financial control for recurring inbound OEM/customer warranty and quality debits.`

Flow now exercised synthetically end-to-end:
PILOT INTAKE → SCOPE → ACCEPTANCE EVIDENCE → DATA AUTHORIZATION → SOURCE DOCUMENT → CLAUSE CANDIDATES → HUMAN REVIEW → APPROVED RULES/PROVENANCE → APPLICABLE CONTRACT VERSION → DEBIT + EVIDENCE → WARRANTY/COST/RESPONSIBILITY/EXCLUSION/DUPLICATE/CREDIT/DEADLINE ANALYSIS → SUPPORTED/PARTIALLY_SUPPORTED/DISPUTABLE/UNKNOWN/RESOLVED → CASE DOSSIER → SAVE/RETURN/OUTCOME → OPERATOR MONITORING → BILLING SANDBOX → SUPPORT.

Truth invariants:
- DEBIT != LIABILITY.
- Candidate clause != legal conclusion.
- Missing/ambiguous material truth => UNKNOWN / NEEDS REVIEW.
- UNKNOWN exposes no supported/disputable money.
- NFF requires explicit contractual rule.
- Exclusions require reviewed evidence facts; absence is not assumed.
- Exact duplicate and potential duplicate are distinct.
- Prior credit reduces outstanding and may resolve a case; it does not fabricate new disputable value.
- Prior payment != prior credit.
- Draft dispute != submitted dispute != approved credit != received credit/cash.
- Credit/cash are not double counted by default.
- Passed notice deadline => REVIEW_REQUIRED, not automatic loss of right.
- Business-day deadlines are not computed without an applicable calendar rule.

## PRODUCT BOUNDARY
`ASSISTED_LOCAL / CLIENT-HELD WORKSPACE / HUMAN_REVIEW_REQUIRED / NO AUTONOMOUS OEM SUBMISSION`

Implemented within this boundary:
- strict tenant-scoped CSV import, 500-row/2MB pilot bounds;
- text-native document ingestion;
- PDF and DOCX assisted ingestion requiring source hash + human-reviewed extracted text + reviewer/time;
- clause/date/deadline candidates with explicit `CANDIDATES_ONLY` status;
- human clause approval, deterministic rule compilation, conflict rejection and clause/source/dossier provenance;
- conservative warranty/cost/responsibility/exclusion/deadline logic;
- evidence content hashes, claims, reviewer lineage and contradictory-evidence failure;
- exact/potential duplicate separation and resolved-credit protection;
- currency-separated economics and UNKNOWN money suppression;
- draft-only dispute packages and evidence-gated recovery states;
- complete case dossier with source hashes and action state;
- client-held HMAC workspace for integrity, explicitly not confidentiality encryption;
- token-protected localhost operator API / CLI;
- fail-closed assisted pilot intake and prohibited data classes;
- operator-only monitoring queue, no automatic external notification;
- support/incident state machine with P0 evidence requirement;
- billing sandbox with `realExternalInvoice=false`, `realPayment=false`, `revenueRecognized=0`;
- cost-to-serve instrumentation separating assumption from real observed evidence;
- repeat-value ledger where synthetic cycles never prove retention;
- executable A–R completion evaluator preventing false project completion.

Public/multi-user customer-data SaaS remains explicitly NOT proven. AuthN/AuthZ, secure shared persistence/secrets, production backup/restore, cloud deletion/retention, observability/rollback and independent production cross-tenant proof require a separate public-deployment gate if that product mode is pursued.

## PERMANENT COMPLETION GATES — CURRENT TRUTH
A DOCUMENTS = `PASS_ASSISTED_LOCAL` — text + assisted PDF/DOCX source lineage handled; broader document classes may be added from real pilot evidence.
B EXTRACTION = `PASS_ASSISTED_HUMAN_REVIEWED` — clauses/dates/deadline candidates traceable; no autonomous legal conclusion.
C WARRANTY LOGIC = `PASS_FOR_CURRENT_WEDGE_FAIL_CLOSED` — warranty/cost/responsibility/exclusion/deadline rules conservative.
D EVIDENCE = `PASS_FOR_CURRENT_WEDGE` — hashes, reviewer lineage, source/contract/clause provenance.
E FALSE-CLAIM CONTROL = `PASS_CURRENT_REDTEAM / CONTINUOUS`.
F CALCULATIONS = `PASS_CURRENT_WEDGE` — multi-currency truth, outstanding/resolved credit, recovery bounds.
G CASE = `PASS_SYNTHETIC_E2E / REAL_CASE_NOT_YET_OBSERVED`.
H PRODUCT = `PASS_ASSISTED_LOCAL_SYNTHETIC_JOURNEY` — intake through support is executable; no public self-service claim.
I SECURITY = `PASS_ASSISTED_LOCAL_BOUNDARY / PUBLIC_MULTIUSER_NOT_PROVEN`.
J BILLING = `PASS_SANDBOX_LIFECYCLE / REAL_EXTERNAL_BILLING_NOT_PROVEN`.
K SUPPORT = `PASS_ASSISTED_WORKFLOW / REAL_SUPPORT_NOT_YET_EXERCISED`.
L OPERATIONS = `PASS_ASSISTED_LOCAL_MONITORING_INCIDENT_WORKFLOW`.
M PILOT = `TECHNICALLY PILOT-CAPABLE_ASSISTED_LOCAL / NOT PROVEN WITH REAL CUSTOMER`.
N VALUE = `NOT_PROVEN_REAL`.
O COMMERCIAL = `NOT_PROVEN_REAL / NO PAID PILOT`.
P RETENTION = `NOT_PROVEN_REAL`.
Q ECONOMICS = `INSTRUMENTED / REAL COST-TO-SERVE NOT YET OBSERVED`.
R QUALITY = `PASS_ON_VERIFIED_LOGIC_HEAD / NO KNOWN OPEN P0 IN ASSISTED_LOCAL BOUNDARY`.
PROJECT_COMPLETE = `NO`.

The executable completion evaluator requires real evidence for M/N/O/P/Q. Internal/synthetic evidence cannot promote those gates.

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

Real first-touch exposures:
1. AFIA → `info@afia.pt` → Gmail `1a04dd405f82f212` → SENT
2. Simoldes → `alexandre.batista@simoldes.com` → Gmail `1a04dd750c85a135` → SENT
3. FEHST → `fehst.comp@fehstgroup.com` → Gmail `1a04df7aca576132` → SENT
4. PLASTIFA → `plastifa@plastifa.pt` → Gmail `1a04df81b959496f` → SENT

LATEST_RESPONSE_CHECK = `2026-09-01` — each thread contained exactly one message, our outbound message. Observable reply/bounce = `NONE`. Silence = `NO_REPLY_YET`, never rejection or demand proof.

## PORTUGAL OUTREACH COMPLIANCE
PORTUGAL_OUTREACH_STATE = `LEGAL_HOLD_DGC_LIST_PENDING`.
The date `2026-09-03` remains only the earliest timing threshold; it is **not authorization to send**.

No Portuguese unsolicited corporate follow-up/new cold email may be sent until all are true:
1. the current applicable DGC corporate opt-out list or authoritative DGC checking procedure is obtained;
2. the intended target is checked and is not suppressed;
3. the live thread has no reply, bounce, rejection, reroute or direct opt-out;
4. no portfolio suppression/collision exists;
5. the message preserves an opt-out route and requests no sensitive customer data by ordinary email.

Current DGC state: requests for the list/procedure already exist in Gmail; as of 2026-09-01 no responsive message providing the current list/procedure was found. Do not duplicate requests merely to create activity. Unknown compliance state = HOLD.

## DONE — MATERIAL
- v0.9.0 source-document truth for native text + assisted PDF/DOCX;
- human-reviewed clause candidates → explicit rules with provenance;
- conservative deadline and exclusion evaluation;
- prior-credit `RESOLVED` protection and outstanding economics;
- 16-case document adversarial matrix;
- synthetic intake→support customer E2E;
- assisted-local security red-team with causal bounded readiness probe;
- save/track/return client-held workspace with audit/HMAC integrity;
- operator monitoring, support/incident flow and billing sandbox;
- cost-to-serve and repeat-value truth-safe measurement primitives;
- executable A–R completion gate;
- minimum data request, onboarding, deletion/return, economics and retention runbooks;
- GitHub CI exact-head verification and CI artifact packaging + clean-extraction reverify;
- verified v0.9.0 source tar persisted in Library;
- Portugal DGC outbound compliance gate persisted and enforced by `npm run verify`.

## ACTIVE
`DGC_RESPONSE_OR_COMPLIANT_CHANNEL + REAL_PILOT_ACQUISITION + RESPONSE_QUALIFICATION + REAL_EVIDENCE_GATES_M/N/O/P/Q`

## NEXT
1. continue checking the four real market lanes and classify only real inbound evidence;
2. monitor existing DGC request threads for the current list/procedure; do not duplicate the request while unchanged;
3. only after DGC compliance is proven, re-check target suppression + thread truth and then consider a follow-up on/after the timing threshold;
4. if direct Portuguese email remains legally held, pursue only lawful non-held channels/inbound/referrals/association routes rather than bypassing the hold;
5. convert a qualified buyer into a bounded paid diagnostic/pilot using the assisted-local intake boundary;
6. process the first authorized real case without placing confidential customer data in public GitHub;
7. measure real intended value, real manual cost-to-serve, payment truth and repeat-cycle evidence;
8. repair every product/process weakness exposed by the real pilot;
9. pursue public multi-user SaaS only if/when justified; never reuse assisted-local security evidence as production proof;
10. do not declare PROJECT COMPLETE until all applicable A–R gates pass with required real evidence.

## WAIT / OWNER-ONLY / EXTERNAL DEPENDENCIES
- Portugal unsolicited corporate email follow-up/new outbound is held pending current DGC suppression-list/procedure evidence and target check.
- M/N/O/P/Q require external customer behavior and evidence; cannot be synthesized.
- Binding contracts/legal signatures, KYC/banking/payment activation and any irreversible customer/OEM authority remain owner-only when reached.
- Formal commercial-name clearance for DebitProof remains unresolved.
- These dependencies do not block compliant inbound handling, association/referral routes, pilot preparation or repository-safe hardening.

## SECURITY_STATE
`ASSISTED_LOCAL_GREEN / PUBLIC_MULTIUSER_NOT_PROVEN_AND_NOT_CLAIMED`

## UNRESOLVED_ASSUMPTIONS
- real customer document/debit formats and contract variation are not yet observed;
- real pilot data-handling constraints may require narrower scope or additional controls;
- WTP, observed cost-to-serve and repeat-value are unproven;
- DebitProof is a provisional working commercial name pending formal clearance.

## RESUME_AT
`EXACT_LATEST_HEAD_CI → MONITOR_4_THREADS + DGC_THREADS → IF_DGC_LIST_AVAILABLE_CHECK_TARGETS → ELSE_KEEP_PORTUGAL_OUTBOUND_HOLD → QUALIFIED_LAWFUL_CHANNEL → BOUNDED_PAID_DIAGNOSTIC → REAL_CASE → REAL_VALUE → REAL_PAYMENT → REAL_REPEAT → REPAIR_DISCOVERED_WEAKNESSES → REEVALUATE_A_TO_R → CONTINUE_UNTIL_PROJECT_COMPLETE`
