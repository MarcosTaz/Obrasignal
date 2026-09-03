# GuaranteeRelease — Canonical Status

Date: 2026-08-29
Source branch: `factory/guaranteerelease`
T1 truth successor: `guaranteerelease/v5-t1-truth-20260829`

## Canonical components

Use these components for all further product/pilot work:

- `FORENSIC_VALIDATION.md` — current business validation / frozen wedge.
- `OPERATING_MODEL.md` — assisted offer and controlled delivery model.
- `SYNTHETIC_ORACLE.json` — independent seven-case ground truth.
- `engine_v3.mjs` — current assessment engine candidate.
- `engine_v3.test.mjs` — current engine safety/oracle suite.
- `server_v5.mjs` — current persistent prototype server and reviewed-evidence workflow.
- `server_v5.test.mjs` — current role/authority/tenant/API suite.
- `app_v5.html` — current controlled-pilot UI.
- `synthetic_replay_v5.test.mjs` — reviewed-baseline seven-case HTTP replay.
- `backup_tools.mjs` / `backup_tools.test.mjs` — controlled backup/restore.
- `AUTH_MODEL.md` — current prototype principal/role boundary.
- `EVIDENCE_RETENTION_POLICY.md` — current evidence-retention boundary.
- `BROWSER_E2E_V5.md` — controlled Chromium DOM/runtime evidence.
- `V5_VERIFICATION.md` — current verification scoreboard.

All earlier app/server/engine versions are historical/superseded and must not be extended.

## Current business state

THESIS_STATE = NARROW_PROMOTED
CURRENT_WEDGE = Contractor-side independent release/reduction recoverability assurance for construction/EPC/infrastructure security portfolios.
GENERIC_GUARANTEE_MANAGEMENT_WEDGE = REJECTED_AS_TOO_CROWDED
MATERIALITY_STATE = PROVEN_AT_LARGE_ENTERPRISE_SCALE
WTP_STATE = UNPROVEN
REAL_ACTIONABLE_PORTFOLIO_RATE = UNKNOWN

## Current engineering state

ENGINE_V3 = PASS_23_OF_23
SERVER_V5 = PASS_38_OF_38
SYNTHETIC_REVIEWED_EVIDENCE_REPLAY_V5 = PASS_41_OF_41
BROWSER_DOM_RUNTIME_V5 = PASS_31_OF_31_TRANSPORT_BRIDGED
BACKUP_RESTORE = VERIFIED_BY_COMMITTED_SUITE
NODE_SYNTAX = PASS
HTML_PARSE = PASS
INLINE_JS_SYNTAX = PASS
OBRASIGNAL_QUALITY_AT_SOURCE_HEAD_F348E089 = SUCCESS

Native browser HTTP on this host remains `BLOCKED_BY_ADMIN_POLICY`; browser DOM/JavaScript ran in real Chromium while requests were bridged through the actual v5 HTTP API. This is not represented as native-network success.

## v5 truth boundary

The current candidate prevents an operator from manufacturing release truth:

1. instrument baseline is not trusted merely because an operator entered it;
2. `INSTRUMENT_TERMS` requires independent reviewer approval before a non-UNKNOWN assessment;
3. approved baseline fields must match the instrument identity/economics;
4. changing a baseline field invalidates prior baseline truth until fresh review;
5. operator and reviewer are separate roles/principals;
6. ambiguous principal configuration and plaintext legacy API-key configuration fail closed;
7. pending evidence does not influence assessment;
8. wrong-project / wrong-contract evidence cannot be approved and forces UNKNOWN until rejected;
9. only approved evidence enters the assessment engine;
10. bank/surety cancellation and collateral release remain separate evidence classes/economic outcomes;
11. expiry can create only a bounded release-due signal after reviewed baseline evidence and never manufactures a release amount;
12. writes and review actions preserve principal provenance in audit history.

## T1 gate

CURRENT_TERMINAL = `T1_PILOT_CAPABLE_ASSISTED_LOCAL`
NEXT_TERMINAL = `T2_MARKET_EXPOSED`
T1_STATE = VERIFIED_FOR_CONTROLLED_ASSISTED_LOCAL_PILOT

T1 is supported by the current synthetic/control evidence:

- evidence-first assessment engine;
- separate operator/reviewer authority;
- tenant isolation and wrong-scope fail-closed behavior;
- controlled datastore persistence;
- backup/restore verification;
- seven-case synthetic replay through actual reviewed-evidence HTTP workflow;
- browser DOM/runtime execution with desktop/mobile inspection;
- explicit reviewer/evidence-retention operating procedures;
- no known P0/P1 in the committed v5 verification set.

T1 does **not** mean production-ready, market-validated, pilot-validated or commercially ready.

## Remaining production/pilot gaps

- production IAM / SSO / MFA;
- production-grade document ingestion with immutable source-content hashing;
- native-browser-network verification in an environment not blocked by URL policy;
- real customer authorization/data handling;
- real portfolio economics and actionable rate;
- real counterparty/bank/surety outcome verification;
- production deployment/secrets/monitoring/billing.

## Commercial truth

REAL_CUSTOMERS = 0
REAL_SECURITY_ANALYZED = 0
REAL_REDUCTION_IDENTIFIED = 0
VERIFIED_REAL_REDUCTION = 0
REAL_COLLATERAL_RELEASED = 0
REAL_CAPACITY_RESTORED = 0
REAL_VERIFIED_SAVING = 0
REVENUE_RECEIVED = 0
WTP = UNPROVEN

Synthetic outcomes are not commercial proof.
