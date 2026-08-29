# GuaranteeRelease — Canonical Status

Date: 2026-08-29
Branch: `factory/guaranteerelease`

## Canonical components

Use these components for all further work:

- `FORENSIC_VALIDATION.md` — current business validation / frozen wedge.
- `OPERATING_MODEL.md` — assisted offer and controlled delivery model.
- `SYNTHETIC_ORACLE.json` — independent initial ground truth.
- `engine_v2.mjs` — canonical assessment engine.
- `engine_v2.test.mjs` — canonical engine oracle + red-team suite.
- `server_v4.mjs` — canonical persistent prototype server and reviewed-evidence workflow.
- `server_v4.test.mjs` — canonical reviewer-authority / tenant-isolation suite.
- `app_v4.html` — canonical controlled pilot UI.

## Superseded prototypes

Historical only; do not extend:

- `index.html`
- `engine.mjs`
- `engine.test.mjs`
- `server.mjs`
- `server.test.mjs`
- `app_v2.html`
- `server_v2.mjs`
- `server_v2.test.mjs`
- `app_v3.html`
- `server_v3.mjs`
- `server_v3.test.mjs`

They are preserved as audit history of the Factory's corrections, not as production candidates.

## Current business state

THESIS_STATE = NARROW_PROMOTED
CURRENT_WEDGE = Contractor-side independent release/reduction recoverability assurance for construction/EPC/infrastructure security portfolios.
GENERIC_GUARANTEE_MANAGEMENT_WEDGE = REJECTED_AS_TOO_CROWDED
MATERIALITY_STATE = PROVEN_AT_LARGE_ENTERPRISE_SCALE
WTP_STATE = UNPROVEN
REAL_ACTIONABLE_PORTFOLIO_RATE = UNKNOWN

## Current engineering state

ENGINE_V2 = PASS_20_OF_20_LOCAL_ASSERTIONS
SERVER_V4_REVIEWER_AUTHORITY = PASS_20_OF_20_LOCAL_ASSERTIONS
NODE_SYNTAX = PASS
HTML_PARSER = PASS
INLINE_JS_SYNTAX = PASS
BROWSER_VISUAL_E2E = NOT_FULLY_VERIFIED

The v4 prototype prevents the operator from manufacturing verified truth:

1. raw instruments can be created without implied evidence;
2. evidence submission is `PENDING`;
3. pending evidence does not influence assessment;
4. a separately authenticated `reviewer` role is required to approve evidence;
5. wrong-project / wrong-contract evidence cannot be approved and forces a fail-closed state until rejected;
6. only approved evidence enters the assessment engine;
7. bank/surety cancellation and collateral release remain separate evidence classes and separate economic outcomes;
8. tenant data and audit retrieval are isolated by server-side tenant authority.

## T1 gate

CURRENT_TERMINAL = T0 — THESIS SURVIVED / WEDGE NARROWED
NEXT_TERMINAL = T1 — PILOT CAPABLE
T1_STATE = NOT_FULLY_VERIFIED

Remaining material T1 requirements:

- real browser/visual E2E execution of `app_v4 + server_v4`;
- backup/restore verification for the controlled datastore;
- stronger prototype authentication/secrets handling before any external pilot;
- explicit reviewer operating procedure and evidence-source retention policy;
- end-to-end synthetic portfolio replay through the reviewed-evidence API, not just direct engine tests.

## Commercial truth

REAL_CUSTOMERS = 0
REAL_SECURITY_ANALYZED = 0
REAL_REDUCTION_IDENTIFIED = 0
VERIFIED_REAL_REDUCTION = 0
REAL_COLLATERAL_RELEASED = 0
REAL_CAPACITY_RESTORED = 0
REAL_VERIFIED_SAVING = 0
REVENUE_RECEIVED = 0

Synthetic outcomes are not commercial proof.
