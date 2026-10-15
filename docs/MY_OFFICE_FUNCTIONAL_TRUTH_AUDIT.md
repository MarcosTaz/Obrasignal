# My Office V24 — Evidence-based functional routing audit
Date: 2026-10-15
Scope: `mobile/src/api.js`, `mobile/App.web.js`, authenticated application.

| My Office area | Actual canonical capability | Wiring status |
|---|---|---|
| Radar | `api.opportunities`, `api.stats` and existing `RadarPanel` | Supported: route `radar` |
| Company/Profile | `api.profile`, `api.saveProfile` and existing `ProfilePanel` | Supported: route `profile` |
| Dossiers/Evidence | No dedicated `api.dossiers` method in inspected client | Blocked: do not invent endpoint |
| Portfolio | No portfolio API in inspected client | Blocked |
| Commercial Export | `api.accountExport` is an ACCOUNT data export, **not** a commercial dossier export | Blocked: do not relabel GDPR export |
| Context | Explanations exist through `OpportunityExplanation` attached to an opportunity | Requires explicitly selected opportunity, not a global fake route |
| Next Action | `api.workflow` and `api.setWorkflow` are opportunity-scoped | Requires selected opportunity; do not update arbitrary records |

Security: all navigation stays under existing `AuthGate`, with current tenant-scoped API. Never imitate a successful write for unsupported functions. The original binary art remains unavailable inside the branch and the feature is disabled by default.

Release acceptance still requires approved binaries installed at `mobile/public/assets/my-office/`, 6 additional independently calibrated geometry maps, responsive interaction tests, keyboard focus and visual comparison, API-backed routes, signed-in E2E and isolation verification.
