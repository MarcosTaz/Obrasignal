# ObraSignal production audit

## Remediated

- account-scoped company profile during canonical decisioning
- explicit account profile scoring
- multi-account sync decisioning
- authenticated legacy/direct routes
- account-scoped radar enrichment
- account-scoped notification events and alert delivery
- mobile/API decision contract alignment
- account-scoped dashboard aggregates (`/api/v1/stats`)
- Google Play / StoreKit subscription architecture through RevenueCat
- 14-day pilot and server-side entitlement enforcement
- web deployment pipeline with GitHub Pages
- production Render auth mode explicitly set to `provider`
- production web CORS origin and Render HTTP health check
- browser-safe billing and notification behaviour
- browser Supabase redirect/session handling

## Still requiring external validation/configuration

- Real Supabase production configuration and end-to-end auth test
- GitHub Pages runtime build variables (`EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`)
- Render JWT issuer/audience/JWKS secrets
- Real web browser acceptance test against production services
- Server push delivery
- Production EAS release gate and store submission (deferred until web acceptance is complete)
- Explicit multi-user company membership
- Real RevenueCat / store purchase, restore, cancellation and expiry validation

## Release principle

No production release should be treated as ready until the applicable authentication, entitlement, notification, release-build and account-isolation gates are green. Web release must additionally prove a real browser session, authenticated API access, opportunity loading, scoring/explanation, workflow persistence and account isolation.
