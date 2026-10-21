# GuaranteeRelease — BATON

Frozen: 2026-08-29
Branch: `factory/guaranteerelease`
HEAD_BEFORE_BATON: `8535feab4358fc852a25e40c869723f5c5650475`

## MISSION

Build and operate a contractor-side independent release/reduction recoverability company for bank guarantees, surety bonds and related collateral/capacity, with evidence-first truth, verified downstream outcomes, near-zero balance-sheet capital, and continuous monitoring.

## CURRENT_TERMINAL

T0 — THESIS SURVIVED / NARROWED WEDGE

## NEXT_TERMINAL

T1 — PILOT CAPABLE

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
- `engine_v2.mjs`
- `engine_v2.test.mjs`
- `server_v4.mjs`
- `server_v4.test.mjs`
- `app_v4.html`
- `backup_tools.mjs`
- `backup_tools.test.mjs`
- `synthetic_replay_v4.test.mjs`
- `CANONICAL_STATUS.md`

All earlier app/server/engine versions are historical/superseded and must not be extended.

## DONE

1. Forensic external validation completed sufficiently to narrow/promote the wedge.
2. Major generic competition identified; system-of-record positioning rejected.
3. Construction/EPC/infrastructure selected as initial industry hypothesis.
4. Advance-payment guarantees ranked as first instrument wedge, followed by performance and retention/warranty instruments.
5. Assisted offer and minimum operation defined.
6. Independent 7-case synthetic oracle created.
7. Canonical engine hardened after red-team defects.
8. Engine v2 local test result: `PASS 20/20`.
9. Persistent tenant-bound prototype built.
10. P0 client-authority flaw discovered: client could previously assert verified evidence/cancellation.
11. P0 repaired: v4 uses PENDING evidence plus separate reviewer authority.
12. Reviewer-authority suite: `PASS 20/20`.
13. Tenant isolation verified in tests.
14. Wrong-project evidence fails closed and cannot be reviewer-approved.
15. Bank/surety cancellation remains separate from collateral release.
16. Backup/restore with SHA-256 manifest and explicit overwrite: `PASS 8/8`.
17. Seven oracle cases replayed through actual reviewed-evidence HTTP workflow: `PASS 23/23`.
18. Node syntax checks: PASS.
19. HTML parser check: PASS.
20. Inline JS syntax check: PASS.

## TEST STATE

ENGINE_V2 = PASS_20_OF_20
REVIEWER_AUTHORITY_V4 = PASS_20_OF_20
BACKUP_RESTORE = PASS_8_OF_8
SYNTHETIC_REVIEWED_EVIDENCE_REPLAY = PASS_23_OF_23
NODE_SYNTAX = PASS
HTML_PARSE = PASS
INLINE_JS_SYNTAX = PASS
BROWSER_VISUAL_E2E = NOT_FULLY_VERIFIED

P0 = 0 KNOWN OPEN IN CURRENT CANONICAL TEST SET
P1 = 0 KNOWN OPEN IN CURRENT CANONICAL TEST SET

## MATERIAL CORRECTIONS MADE DURING THIS SLICE

- v1 engine accepted impossible amount/percentage states; repaired in v2.
- v2/v3 API allowed client-originated evidence-verification truth; repaired in v4.
- v2 UI automatically marked repayment evidence verified; rejected and superseded.
- v4 requires two-step evidence submission/review and keeps wrong-identity evidence fail-closed.

## ACTIVE

`T1 browser/visual E2E verification of app_v4 + server_v4, then close or repair any UI/runtime findings.`

## NEXT

If browser E2E is green:

1. freeze T1;
2. define controlled pilot runbook and evidence-retention requirements;
3. harden prototype auth/secrets beyond environment JSON mapping;
4. package a diversified synthetic portfolio import workflow;
5. expose a non-production demo safely;
6. begin T2 market-exposure preparation without claiming WTP/customer proof.

If browser E2E finds a regression, regression repair becomes ACTIVE immediately.

## WAIT / BLOCKER

BROWSER_VISUAL_E2E is currently blocked in this execution environment because the expected browser automation CLI is unavailable. HTTP integration, parser and JS syntax verification were performed instead, but they do not substitute for a real browser pass.

This local blocker does not invalidate completed test evidence and must not be interpreted as Factory completion.

## OWNER-ONLY / SENSITIVE DEPENDENCIES

None required for current local/synthetic development.

Any future real customer outreach, customer-data ingestion, production deployment, bank/surety communication or irreversible external action must preserve authorization boundaries and cannot be fabricated as completed.

## RESUME_AT

Run real browser E2E against `server_v4.mjs` serving `app_v4.html` with two test identities (`operator` and `reviewer`). Exercise:

1. operator login;
2. create base instrument;
3. submit reduction-rule evidence;
4. submit repayment evidence;
5. verify both remain PENDING and do not change potential value;
6. reviewer login;
7. approve each evidence object;
8. confirm state becomes `REDUCTION_EVIDENCE_SUPPORTED` only after both approvals;
9. submit wrong-project evidence and confirm UI displays `UNKNOWN`;
10. reviewer must be unable to approve mismatched evidence;
11. reject mismatch and confirm prior truth is restored;
12. visually inspect mobile/responsive layout, console errors and audit rendering.

Do not restart validation or redesign the wedge before executing this resume action unless new evidence forces it.
