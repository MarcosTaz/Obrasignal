# GuaranteeRelease — v5 Browser / Runtime Verification

Date: 2026-08-29
Candidate: `engine_v3.mjs` + `server_v5.mjs` + `app_v5.html`

## Executed result

`PASS BROWSER V5 31/31 (TRANSPORT-BRIDGED)`

A real Chromium 144 browser executed the actual v5 DOM/JavaScript. Relative application requests were carried by a CDP test binding to the actual `server_v5.mjs` HTTP API because the runtime blocks native browser navigation/networking with administrator policy.

Verified behavior includes operator authentication and role-aware controls; new instrument starts `UNKNOWN`; baseline evidence stays PENDING/UNKNOWN; reviewer cannot create/submit; approved baseline unlocks assessment; pending rule+repayment remain zero; rule alone remains `REDUCTION_MAY_BE_DUE`; reviewed baseline+rule+repayment produces the expected evidence-supported reduction; wrong-project evidence forces `UNKNOWN`; mismatched evidence cannot be approved; rejection restores prior reviewed truth; principal provenance appears in evidence/audit; desktop and mobile have no page-level overflow; browser runtime exceptions, console errors/asserts and browser error logs are all zero.

## Native-browser HTTP limitation

`NATIVE_BROWSER_HTTP = BLOCKED_BY_ADMIN_POLICY` on this host. Chromium is managed with wildcard URL blocking that prevents localhost, file/data and external navigation before application networking can run. The system policy was not modified.

Therefore the browser test used CDP only as request transport. App JavaScript, DOM, server implementation, authentication/authorization and server responses were not replaced by mocks. Native HTTP/API behavior is independently exercised by Node integration suites.

This is strong controlled-prototype evidence, but it is **not** represented as a native-browser-network PASS on this host.

## Visual inspection

Desktop (1200px) and mobile (390px) captures were inspected. Truth-state panels are legible, disabled reviewer-forbidden actions are visibly muted, and the mobile portfolio table remains inside its own scroll container instead of creating page-level overflow.
