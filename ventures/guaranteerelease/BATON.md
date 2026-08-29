# GuaranteeRelease — BATON

Frozen: 2026-08-29
Source branch: `factory/guaranteerelease`
T1 truth successor: `guaranteerelease/v5-t1-truth-20260829`
Verified source HEAD before truth reconciliation: `f348e0896885c6d59055d3ec20e84814ecd9a577`

## MISSION

Build and operate a contractor-side independent release/reduction recoverability company for bank guarantees, surety bonds and related collateral/capacity, with evidence-first truth, verified downstream outcomes, near-zero balance-sheet capital, and continuous monitoring.

## CURRENT_TERMINAL

`T1_PILOT_CAPABLE_ASSISTED_LOCAL`

## NEXT_TERMINAL

`T2_MARKET_EXPOSED`

## CURRENT_WEDGE

Construction / EPC / infrastructure contractor security portfolios: independently reconcile instrument + governing contract + project evidence to identify evidence-supported reductions/releases and verify bank/surety/collateral outcomes without replacing the customer's TMS/ERP/bank portal.

## BUSINESS TRUTH

- Broad generic guarantee-management software wedge: REJECTED_AS_TOO_CROWDED.
- Narrow independent recoverability assurance wedge: PROMOTED.
- Materiality: PROVEN at large-enterprise portfolio scale.
- Near-zero-capital assisted-delivery feasibility: PASS.
- WTP: UNPROVEN.
- Typical actionable/releasable percentage in a real customer portfolio: UNKNOWN.
- Real customers: 0.
- Real security analyzed: 0.
- Real verified reduction/release: 0.
- Real collateral released: 0.
- Real capacity restored: 0.
- Revenue received: 0.

## CANONICAL TECHNICAL COMPONENTS

- `FORENSIC_VALIDATION.md`
- `OPERATING_MODEL.md`
- `SYNTHETIC_ORACLE.json`
- `engine_v3.mjs`
- `engine_v3.test.mjs`
- `server_v5.mjs`
- `server_v5.test.mjs`
- `app_v5.html`
- `backup_tools.mjs`
- `backup_tools.test.mjs`
- `synthetic_replay_v5.test.mjs`
- `AUTH_MODEL.md`
- `EVIDENCE_RETENTION_POLICY.md`
- `BROWSER_E2E_V5.md`
- `V5_VERIFICATION.md`
- `CANONICAL_STATUS.md`

Earlier versions are historical/superseded and must not be extended.

## DONE

1. Forensic external validation narrowed/promoted the wedge.
2. Generic system-of-record positioning was rejected.
3. Construction/EPC/infrastructure selected as initial industry hypothesis.
4. Advance-payment guarantees ranked as first instrument wedge, followed by performance and retention/warranty instruments.
5. Assisted offer and minimum operation defined.
6. Independent seven-case synthetic oracle created.
7. Baseline/economic engine hardened through v3.
8. `engine_v3.test.mjs`: PASS 23/23.
9. Persistent tenant-bound v5 prototype built.
10. Client-originated verified evidence/cancellation authority removed.
11. v5 requires independently reviewed `INSTRUMENT_TERMS` before a non-UNKNOWN baseline assessment.
12. Operator/reviewer role separation and principal provenance implemented.
13. Ambiguous principal configuration and plaintext legacy API keys fail closed.
14. Tenant isolation and wrong-project/wrong-contract review rejection implemented.
15. Bank/surety cancellation remains separate from collateral release.
16. Backup/restore with manifest integrity and explicit overwrite is verified by committed suite.
17. Seven oracle cases replayed through actual reviewed-evidence v5 HTTP workflow: PASS 41/41.
18. `server_v5.test.mjs`: PASS 38/38.
19. Real Chromium executed actual v5 DOM/JavaScript: PASS 31/31 transport-bridged.
20. Desktop/mobile visual inspection found no page-level overflow; browser runtime exceptions/console errors were zero.
21. Source HEAD `f348e0896885c6d59055d3ec20e84814ecd9a577` passed ObraSignal Quality.
22. Canonical status was reconciled from stale v4/T0 wording to verified v5/T1 truth on this successor.

## TEST STATE

ENGINE_V3 = PASS_23_OF_23
SERVER_V5 = PASS_38_OF_38
SYNTHETIC_REVIEWED_EVIDENCE_REPLAY = PASS_41_OF_41
BROWSER_DOM_RUNTIME = PASS_31_OF_31_TRANSPORT_BRIDGED
NATIVE_BROWSER_HTTP = BLOCKED_BY_ADMIN_POLICY
BACKUP_RESTORE = VERIFIED_BY_COMMITTED_SUITE
NODE_SYNTAX = PASS
HTML_PARSE = PASS
INLINE_JS_SYNTAX = PASS
SOURCE_HEAD_QUALITY = SUCCESS

P0 = 0 KNOWN OPEN IN CURRENT V5 VERIFICATION SET
P1 = 0 KNOWN OPEN IN CURRENT V5 VERIFICATION SET

## PRODUCT TRUTH

The v5 candidate is capable of supporting a bounded assisted local pilot with separately authenticated operator/reviewer roles, reviewed baseline truth, evidence-gated assessment, tenant isolation, audit provenance, backup/restore and a browser-executed UI. It is not production-grade IAM/document-ingestion infrastructure and it does not establish any real-world entitlement or release.

## ACTIVE

Prepare T2 market-exposure and real-pilot admission assets without contacting a real prospect or ingesting real customer data.

## NEXT

1. Freeze a narrow first-pilot ICP/qualification screen.
2. Freeze external exposure and real-pilot evidence gates.
3. Prepare a reversible operator/exposure pack with no named prospect.
4. Define production-readiness dependencies separately from T2 exposure.
5. If real exposure is later authorized, preserve exact named-prospect/transmission/response truth.

## WAIT / EXTERNAL

- Real customer/prospect outreach or transmission.
- Real security portfolio/customer data.
- Production IAM/SSO/MFA and production document-ingestion infrastructure.
- Native-browser HTTP retest on a host without administrator URL blocking.
- Production deploy/secrets/bank/surety communication/billing.

## RESUME_AT

Complete T2 preparation artifacts. If all remaining steps require external/customer/production authority, move to the next portfolio Factory rather than overbuilding this lane.
