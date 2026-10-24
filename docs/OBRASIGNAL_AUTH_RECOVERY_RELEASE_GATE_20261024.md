# OBRASIGNAL — Auth recovery release gates (24 October 2026)

**Status:** BLOCKED FOR CUSTOMER LOGIN / INVITED CUSTOMER ACCESS. Frontend recovery safety code has passed CI, but live auth and email recovery are not restored.

## Verified evidence (read-only)
- The production health endpoint (last verified GitHub production smoke `40027009728`) reports `auth.mode=provider`, `provider_kind=supabase`, `provider_status=degraded`, `provider_error=dns_error`, `runtime.auth_warm_status=degraded`.
- Production target Supabase project reference: `oxvpebrsswqxyfjxaaxg`. Its project is absent from the **currently connected** Supabase organization. Direct project read returned **permission denied**. **Never conclude it is definitively deleted.** Supabase's NXDOMAIN guidance explicitly includes paused projects, wrong project references and deleted projects.
- Current Supabase connection exposes two different healthy projects that are NOT verified as the identity source for OBRASIGNAL. **Never redirect OBRASIGNAL to either.**
- Dedicated Neon candidate `royal-cloud-69492271`, branch `br-old-thunder-b9es5qx1`, database `obrasignal_auth`: **0 users, 0 organizations, 0 memberships, 0 invites** (read-only SQL, 24 Oct). Auth provider configured as Neon-hosted Better Auth. This is an empty destination, not an approved cutover.
- Correct historical Render backend service (prior verified service evidence) is `srv-da24khijnfac73ak3o60` in workspace `tea-da24cnnqj5pc73did9j0`. Currently connected Render workspace `tea-dadnboad0e5s73dkin0g` is a DIFFERENT account/workspace; direct get_service on the correct historical workspace returned **forbidden**. Do not recreate or move the service.
- A targeted search of accessible Google Drive and account messages did not locate a reliable legacy Supabase identity export; absence from search is NOT proof no backup exists.

## Recovery pathway, in safe order
1. **Ownership recovery:** Reconnect the original Supabase account/organization that owns `oxvpebrsswqxyfjxaaxg`, and the Render account whose workspace is `tea-da24cnnqj5pc73did9j0`. Confirm the exact live project references in dashboards, without exposing API keys or exporting real user records into chat. If Supabase is paused, resume from the original owner dashboard; **do not** guess a new project URL.
2. **Inventory before mutation:** Collect read-only counts and secure offline hashes/inventory of user IDs, credential provider metadata, tenant company IDs, role memberships, RLS policies, subscription records and invitations. Verify the original data is in the expected account and take a restorable protected backup; do not disclose customer emails in public logs.
3. **Restore original if possible:** For paused project, resume and retest DNS/HTTPS/JWKS/auth redirects. For permanently unavailable project, stop and choose recovery from a verified historical backup; transfer must map ORIGINAL UID -> new UID one-to-one and ORG + ROLE memberships exactly, reject duplicates/missing users/cross-tenant matches.
4. **Authentication parity:** Verify issuer/audience/JWKS and session TTLs between mobile client and backend. No password or JWT bypasses; invite-only enforced server-side. No other company's identity provider.
5. **Email recovery:** Configure the exact `https://obrasignal.com/?type=recovery` redirect URL in the real Supabase project. Test provider `resetPasswordForEmail` with synthetic approved account, actual inbox receipt, `PASSWORD_RECOVERY` event, temporary cache quarantine, `updateUser`, successful sign-out, then normal login. Check expired/forged URLs and rate limits. Never assert a message was delivered based on reset API returning success (nonexistent accounts can return success).
6. **Tenant isolation:** Using distinct synthetic A/B companies, verify that login, profile, opportunity scores, notes, exports, billing and mobile persistence cannot cross tenants. Restore independent backup as a destructive-recovery rehearsal, not on production accounts.
7. **Deploy only after gates:** Exact production SHA, provider READY, web route/JS compile, CORS and browser recovery test. Keep previous public build available for rollback. No customer invitations, payments or production identity writes before passing all gates.

## Code already prepared in PR #973
- Public health advisory for degraded auth service; no conflation of DNS with invalid credentials.
- Explicit `PASSWORD_RECOVERY` event required in addition to URL; callback is barred from customer-workspace routing and tenant-bound caches.
- Expired / unverified link fails closed.
- Password update confirmation separated from sign-out failure.
- Automated Node tests / Expo Web export / Python QA included.

**Release decision:** DO NOT CLAIM CUSTOMER RECOVERY RESTORED until the original identity provider is accessible and a real end-to-end recovery is verified.
