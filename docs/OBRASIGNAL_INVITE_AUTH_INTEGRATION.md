# ObraSignal private invitation implementation — integration boundary

The invitation authority in `registration_invites.py` is an isolated backend component, modeled on security principles of CERTACTUM, but **does not use** CERTACTUM Neon projects, user records, tables, tokens, domains, mail identities, or billing.

## Evidence (2026-10-15)
- Unit tests: `python -m unittest discover -s tests -p test_registration_invites.py -v`.
- CI: `.github/workflows/invitation-authority.yml`.
- Invitation code is 192 bits of random entropy (24 bytes) and uses `OS-` prefix.
- SQLite stores SHA-256 digest only; code returned exactly once at issue.
- Expiry, email binding, revocation and single-use consumption are tested.
- There is NO unauthenticated invitation-issuance route.

## Important: this is NOT yet a complete signup provider
- Production currently relies on Supabase Auth for login, tokens and recovery.
- This authority **cannot by itself prevent a Supabase signup**, nor sign JWTs.
- Do not call `consume_invite` before a transactionally coordinated account creation flow; otherwise failed provider signup could burn the invite without creating an account.
- Never expose invite administration to the public site or issue invitations using client credentials.
- An existing user registry needs a documented migration plan before any provider replacement.
- Connection pool/SQLite transaction boundaries must be tested with production WAL and concurrency.

## Next secure integration gates
1. Confirm canonical production identity issuer. The configured Supabase project host currently fails DNS.
2. Choose a managed identity authority (e.g. dedicated ObraSignal Neon Managed Auth) and provision distinct tenant, keys and email sender. Do not reuse CERTACTUM or another organization's keys.
3. Bind provider account creation to validated invitation BEFORE any user is activated, with transactional or compensating failure handling, and test parallel redemption.
4. Verify login, password recovery, JWKS signature, audience and issuer, user/tenant isolation and account migration.
5. Perform live anonymous signup rejection, invited acceptance, replay, expiry and revocation tests.
6. Only after above pass, approve and deploy PR #963 and integrate the My Office V27 visual assets.

## Release status
**REVIEW ONLY**. The public production deployment must remain unchanged until provider-level invitation enforcement is verified.
