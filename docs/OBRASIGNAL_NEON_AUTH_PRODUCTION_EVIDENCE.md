# ObraSignal Neon Auth — Verified boundary (2026-10-15)

Dedicated project: `royal-cloud-69492271`, branch `br-old-thunder-b9es5qx1`, DB `obrasignal_auth`.
This is NOT the CERTACTUM project.

## Applied to actual Neon database
- Neon Managed Auth / Better Auth provisioned.
- Table `public.obrasignal_auth_invites` created, with restricted privileges and RLS.
- `public.obrasignal_validate_invited_signup` SECURITY DEFINER trigger installed BEFORE INSERT ON `neon_auth."user"`.
- Only emails with valid, unused, unexpired, non-revoked `OS-` invitations (192-bit token, SHA-256 digest stored) may be inserted into identity table.
- Invitation protocol: the signup display-name parameter is `OS-<48 hexadecimal chars>|<display name>`. Trigger strips token from persisted display name.
- Trusted DB-owner-only `public.obrasignal_issue_auth_invite(email,issuer,hours)` installed; execute privilege revoked from PUBLIC. No invitation is sent to a customer.
- Fail-closed synthetic SQL proofs: uninvited signup rejected, invited signup succeeds and consumes invitation, token removed from stored name, repeated invitation rejected, wrong email rejected. All synthetic registrations were rolled back.
- This database initially contained zero accounts.

## Remaining integration and safety gates
1. Client still uses Supabase Auth and is not yet using Neon. Do NOT deploy as though provider migration is complete.
2. Test Better Auth REST signup/sign-in/recovery and token verification against this new endpoint, including behavior with the name-based invitation protocol.
3. Add trusted invitation administration/delivery; never expose owner DB connection or issue RPC publicly. Confirm email verification and account enumeration protections.
4. Inventory existing Supabase identities and migrate or invite existing customers before switching issuer, with tenant-ID mapping.
5. Update both frontend auth client and Python JWT verifier, production Render issuer/JWKS settings and Pages build secret. Retire Supabase only after migration.
6. Run live E2E + adversarial + rollback under trusted deployment; verify no unauthorized account or cross-tenant data access.

## Key security note
The Neon provider currently advertises allow_sign_up=true. The database trigger protects the identity INSERT boundary, **but native API denial and account/provider side effects must still be tested**. Do not infer full end-to-end readiness from SQL checks alone.

## Live HTTP findings after provider setup
- Synthetic no-invite POST `/sign-up/email` returned HTTP 422 repeatedly (GitHub workflow `ObraSignal Live Neon Auth Denial` PASS).
- The bounded diagnostic classified the response `UPSTREAM_VALIDATION_OR_UNKNOWN`, **not** a proven trigger rejection. Do not claim that provider-level invitation denial has passed until a valid invited POST succeeds and a corresponding uninvited POST is demonstrably refused by the database gate.
- Verified canonical redirect origin `https://obrasignal.com` is trusted; project display name is `ObraSignal`.
- Read-only DB verification after probes: zero users, zero invitations; signup trigger remains enabled.
