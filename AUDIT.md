# ObraSignal production audit

## Remediated in PR #61

- account-scoped company profile during canonical decisioning
- explicit account profile scoring
- multi-account sync decisioning
- authenticated legacy/direct routes
- account-scoped radar enrichment
- account-scoped notification events and alert delivery
- mobile/API decision contract alignment

## Critical findings still open

- Real Supabase production configuration and end-to-end auth test
- Subscription/entitlement/billing
- Server push delivery
- Production EAS release gate and store submission
- Explicit multi-user company membership
- Account-scoped dashboard aggregate metrics

## Release principle

No production release should be treated as ready until the authentication, entitlement, notification, release-build and account-isolation gates are green.