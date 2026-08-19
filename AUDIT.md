# ObraSignal production audit

This file records the current production-readiness audit and remediation plan. It contains no secrets.

## Critical findings

1. Notification events are global rather than account-scoped, while authenticated alert reads/delivery endpoints operate on that global table.
2. Several legacy/direct Flask routes are registered outside the authenticated API blueprint and can bypass the same account boundary.
3. The mobile UI expects `decision_score` / `decision_reason`, while the API currently emits `account_score` / `account_reason`, so the visible company score can fall back to the global tender score.
4. There are two scoring paths: legacy scoring in `app.py`/`profile_scoring.py` and the canonical commercial matching pipeline. They can disagree.
5. `profile_scoring.py` currently loads the default profile during shared tender scoring, which is unsafe for multi-account personalization.

## High-priority product gaps

- Real Supabase project/environment configuration and an end-to-end authentication test are still required.
- Push notifications are currently local-only; there is no server device-token registration/delivery service.
- Subscription/entitlement/billing is not implemented.
- Store submission metadata and full device QA are not complete.
- The production workflow builds EAS binaries but does not submit them to stores.

## Remediation order

1. Fix account isolation and notification/event boundaries.
2. Remove/retire duplicate scoring paths and make account-specific scoring explicit.
3. Put all externally reachable routes behind the same auth/account context.
4. Align mobile/API contracts and add contract tests.
5. Add production configuration checks and end-to-end authentication tests.
6. Add entitlement/billing and trial controls.
7. Add real push delivery, store release gates and operational monitoring.
