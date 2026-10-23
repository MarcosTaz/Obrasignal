# ObraSignal — P0 authentication recovery, identity continuity, 2026-10-23

## Live evidence, not assumptions
- User-observed login on https://obrasignal.com returns `Failed to fetch` (private 62s recording; NEVER upload credentials or the full recording to public GitHub).
- Production Smoke [#40010911915](https://github.com/MarcosTaz/Obrasignal/actions/runs/40010911915) reaches the actual API but reports `auth.mode=provider`, `provider_kind=supabase`, `provider_status=degraded`, `provider_error=dns_error`, `auth_warm_status=degraded`.
- Radar Readiness [#39987209282](https://github.com/MarcosTaz/Obrasignal/actions/runs/39987209282) cannot resolve `oxvpebrsswqxyfjxaaxg.supabase.co`. This is provider DNS, **not evidence of bad customer passwords**.
- Connected Supabase account lists only CERTACTUM-PRODUCTION and one unverified other project. The missing historical OBRASIGNAL project **must not** be replaced by either without proof of ownership and source identity inventory.
- Dedicated Neon `royal-cloud-69492271`, branch `br-old-thunder-b9es5qx1`, DB `obrasignal_auth`, Better Auth available; read-only counts at audit: **zero users, zero organizations, zero memberships, zero invites**. This is an empty destination, not proof there were never customers.

## Recovery sequence (fail closed)
1. **Locate old source:** recover legitimate former Supabase project/org authority, verified backup or dated identity export. For each legacy identity store immutable old UID, verified email, email-confirmation state, org/company IDs, membership/roles, company ownership, tenant data references, and billing links. Do not infer identity mapping from email alone.
2. **Recover data evidence:** take a consistent export/snapshot with integrity checks and documented source, timestamp, counts; protect personally identifying records and secrets outside GitHub/public PR logs. Preserve password hashes only through a legitimate supported migration path; otherwise use a documented secure re-enrolment route with verified ownership.
3. **Stage on isolated infrastructure:** map each old ID to exactly one new ID, one-to-one company memberships and roles, no orphan companies, no cross-tenant disclosures. Keep unrelated CERTACTUM and other Supabase projects untouched.
4. **Private invitation/auth gate:** require provider-level anonymous signup rejection and a genuinely successful invited signup; UI-only removal is **not** a substitute. Do not unilaterally switch `allow_sign_up` off without a tested replacement for the invited registration flow.
5. **JWT/bearer integration:** verify actual Neon Better Auth JWT issuer, JWKS, algorithms, cookie-to-bearer exchange, backend validation and company membership with exact tenant source of truth. Never pass the provider's session cookie as a trusted API bearer token without verification. PR #963 remains incomplete on this boundary.
6. **Account continuity acceptance:** legacy account signs in; personal company profile and workflows load; invalid/anonymous requests 401/403; cross-company access denied; password recovery works; no duplicate identities; backups restore; rollback reenables the prior validated path without loss.
7. **Only then publish:** require production-like staging E2E on *exact* release SHA, rollback rehearsal, no open registrations, fresh live read-only provider health and company isolation. Release owner must explicitly approve any production migration/merge.

## Current safe frontend mitigation
- `mobile/components/AuthScreen.tsx` no longer offers unaudited direct public Supabase signup; new users request a human-issued invitation.
- `mobile/src/auth-failure-feedback.mjs` translates network/protocol errors into safe Portuguese explanations. It never echoes raw provider errors, URLs or tokens; it never claims an unsuccessful recovery email was sent.
- `mobile/src/auth-failure-feedback.test.mjs` checks network, invalid credentials, rate limits, privacy and no public signUp in the frontend. **Backend anonymous signup remains unproven** and is a P0 blocker.
- This is UX risk reduction, not repair of a missing DNS host. No user accounts were created/deleted/migrated and no DNS/production configuration was changed.

### Related development gates
- [#965](https://github.com/MarcosTaz/Obrasignal/issues/965) — P0 release blocker and dated live evidence.
- [#963](https://github.com/MarcosTaz/Obrasignal/pull/963) — existing Neon/invitation work, NOT ready to deploy.
- [#966](https://github.com/MarcosTaz/Obrasignal/pull/966) — offline identity-map preflight and migration evidence gate.
- [#967](https://github.com/MarcosTaz/Obrasignal/pull/967) — premium brand/theme work, not deployed.
- [#968](https://github.com/MarcosTaz/Obrasignal/pull/968) — public SEO metadata, not deployed.
