# ObraSignal production audit

This file records the current production-readiness audit and the remediation plan. It intentionally contains no secrets.

## Critical findings

1. **Notification events are not account-scoped.** `opportunity_events` has no `account_id`, while the authenticated `/api/v1/alerts` endpoint reads the global event table. Delivery acknowledgement also updates events globally.
2. **Legacy/direct routes are outside the authenticated API blueprint.** `preload.py` registers `/radar`, `/opportunity/<id>`, `/api/v1/source-health`, `/api/v1/latency` and `/api/v1/latency-health` directly on the Flask app. These routes need the same authentication boundary and account-scoped decision lookup.
3. **The mobile UI expects `decision_score` / `decision_reason`, while the API currently returns `account_score` / `account_reason`.** The visible score therefore falls back to the global tender score instead of the company-specific score.
4. **The legacy `app.py` still contains a second scoring implementation.** `preload.py` overrides the TED/BASE fetch functions and applies `profile_scoring.py`, while the canonical commercial decision pipeline is separate. This creates two scoring paths that can disagree.
5. **`profile_scoring.py` loads the default profile rather than the authenticated account profile.** Its current use in `_apply_profile_scores()` can therefore write one account's profile-derived score into the shared tender row.

## High-priority product gaps

- Real Supabase project/environment configuration and end-to-end login test are still required.
- Push notifications are currently local-only; there is no server device-token registration/delivery service.
- Subscription/entitlement/billing is not implemented.
- Store submission metadata and full device QA are not complete.
- The current production workflow builds EAS binaries but does not submit them to stores.

## Remediation order

1. Fix account isolation and notification/event boundaries.
2. Remove/retire duplicate scoring paths and make account-specific scoring explicit.
3. Make all externally reachable routes use the same auth/account context.
4. Align mobile/API contracts and add contract tests.
5. Add production configuration checks and end-to-end authentication tests.
6. Add entitlement/billing and trial controls.
7. Add real push delivery, store release gates and operational monitoring.
