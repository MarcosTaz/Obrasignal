# ObraSignal — Canonical Services and Cleanup Register (2026-10-15)

## Confirmed by repository configuration
- **Code & web deploy:** GitHub repository `MarcosTaz/Obrasignal`; `.github/workflows/web-preview.yml` publishes GitHub Pages from `main` to `obrasignal.com`.
- **API service:** Render blueprint `render.yaml`, service `obrasignal`, endpoint `https://obrasignal.onrender.com/api/v1`.
- **Persistent application state:** Render disk `/var/data`; SQLite file `/var/data/obrasignal.db`.
- **Authentication:** Supabase Auth client `mobile/lib/supabase.ts`, configured by `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` GitHub Actions secrets. Actual production Auth project ID is not yet verified.
- **Analytics:** private endpoint in the backend, invoked from `web-preview.yml`.
- **Commercial provider:** RevenueCat variables exist but checkout is allowed only when configured. Do not assume paid billing is active.
- **DNS registrar:** requires separate authoritative validation; not derivable from `render.yaml` alone.

## Inspected connected accounts (not deletion authorization)
- **Supabase connector:** only `tvmrqhtatgfozvtorhnf`, inactive; **unverified as ObraSignal production**. Never change this project based solely on this observation.
- **Render connector:** current workspace service enumeration returned `null`; the Render blueprint proves intended topology, **not** current connected-account ownership of the live service. Do not delete or recreate any service.
- **Neon org `org-cool-butterfly-55648046`:** projects identified CERTACTUM, AERVIND, NUVAREM, AVERHALL, none explicitly ObraSignal. **Do not touch other projects**.
- **Neon org `org-late-shape-23588571`:** empty.
- No evidence ObraSignal needs a Neon database.

## Isolation and cleanup decisions
- **KEEP (canonical):** GitHub repository, Pages build, DNS domain, Render API + SQLite persistent disk, real production Auth project (pending identification), official transparent SVG assets.
- **VERIFY BEFORE CHANGE:** provider Auth project ID and signup settings, actual Render service account, DNS, payments, custom domains, old auth settings, old Deploy secrets.
- **REMOVE FROM OBRASIGNAL ONLY AFTER VERIFIED NOT REFERENCED:** duplicate preview assets, unrelated project names/references, unused secrets/endpoints, dead feature flags and unused build jobs.
- **DO NOT DELETE:** repositories, users, identities, databases, services, DNS records or payment integrations without dependency proof and rollback plan.

## Server-side invitation completion gate
1. Identify actual production Supabase URL host **without exposing API keys**; match host to a managed Auth project.
2. Disable public email signup in that project.
3. Define an authenticated admin-only invitation creation path with limited-use, expiry and email binding; avoid exposing service role credentials client-side.
4. Prove anonymous signup rejected; valid invite can provision one account; replay/expired/wrong-email rejected; existing sign-in and password reset unaffected.
5. Verify backend access with JWT and tenant separation; then release from draft PR after web/mobile E2E.

## Status
**NOT PRODUCTION READY:** frontend-only removal of `signUp` does not enforce the server-side restriction. GitHub Pages `main` remains unchanged until gates pass.
