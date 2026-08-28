# BATON — Engineering Change Recoverability Assurance

MISSION: prove and build the narrowed independent engineering-change recoverability business.
CURRENT_TERMINAL: T0 — NARROW / SURVIVED
NEXT_TERMINAL: T1 — PILOT CAPABLE
CURRENT_WEDGE: independent recoverability assurance for Tier-1/Tier-2 automotive suppliers; no PLM/ERP/CPQ replacement.
REPOSITORY: MarcosTaz/Obrasignal
BRANCH: factory/engineering-change-recoverability
BASE_MAIN_HEAD: 66d43f6fd51cf9cea08016dad335aaa04b711a24
DONE: forensic validation; direct collision; buyer/trigger evidence; wedge freeze; assisted-offer definition; deterministic recovery engine; 10 synthetic cases; independent oracle; evidence graph/missing-evidence model; append-only SQLite history; signed expiring bearer auth; tenant isolation; concurrent append protection; atomic case+analysis persistence; invalid-input no-partial-write HTTP red-team; restart persistence; backup/restore integrity; commercial action package; local HTTP E2E.
EVIDENCE: academic EC materiality/frequency; public supply agreements linking engineering changes to price/cost/obsolete inventory; current automotive roles explicitly owning EC commercialisation/recovery; Campfire direct competitive collision; public supplier standards showing EC quoting/tooling/PPAP/obsolescence workflow.
ACTIVE: strengthen evidence-content matching for customer/program/part/revision/cost assertions; add adversarial wrong-customer/wrong-program/wrong-part tests; then re-run full oracle + HTTP E2E and decide T1 promotion strictly.
NEXT: persist verified context assertions in evidence objects; reject mismatch fail-closed; test superseded contract/change, duplicate evidence IDs, missing notice proof and prior-payment proof; update dossier; commit next verified slice.
WAIT: real customer data and WTP remain unavailable until legitimate T2 market exposure.
BLOCKER: no external blocker for safe prototype work.
P0: none currently known in the isolated local real-record path after auth/tenant red-team; T1 still withheld because context evidence matching is incomplete and could permit a materially wrong customer/program/part to inherit otherwise valid evidence.
P1: context-identity evidence mismatch detection incomplete; therefore T1 NOT YET PROMOTED.
TEST_STATE: 21 tests pass with ResourceWarning treated as error; HTTP save/analyze/package/history E2E passes; unauthenticated access=401; cross-tenant token read=404.
COMMERCIAL_STATE: T0 evidence only; no paid pilot; no real customer; no verified recovery; no revenue.
MODIFIED_FILES: README.md, VALIDATION.md, RESEARCH_EVIDENCE.md, BATON.md, engine.py, synthetic_cases.json, auth.py, store.py, commercial_package.py, app.py, test_engine.py, test_store.py, test_auth.py, test_commercial_package.py.
UNFINISHED_WORK: context evidence-content matching; additional red-team; repository commit/draft PR; T1 decision; then safe T2 preparation.
RESUME_AT: add evidence assertions for customer/program/part/revisions and cost amount/currency; make engine compare input against those assertions and fail closed on mismatch.
