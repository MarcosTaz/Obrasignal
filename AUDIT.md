# ObraSignal production audit

## Critical findings

1. Notification events are global rather than account-scoped.
2. Several legacy/direct Flask routes bypass the authenticated API blueprint.
3. The mobile UI expects `decision_score` / `decision_reason`, while the API emits `account_score` / `account_reason`.
4. Legacy and canonical scoring paths coexist and can disagree.
5. Shared tender scoring currently loads the default profile instead of an authenticated account profile.

## High-priority gaps

- Real Supabase project/environment configuration and end-to-end authentication test.
- Server device-token registration and remote push delivery.
- Subscription/entitlement/billing.
- Store submission metadata and full device QA.
- Production release gates and monitoring.
