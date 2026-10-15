# ObraSignal — Email identity and invitation launch gate (2026-10-15)

## Verified actual configuration
- Public contact address in mobile/components/AuthScreen.tsx: `obrasignal.pt@gmail.com`.
- Dedicated Neon Auth project `royal-cloud-69492271`, branch `br-old-thunder-b9es5qx1`: email provider is **shared**.
- Configured sender: `auth@mail.myneon.app`, sender name: `Neon Auth`.
- Trusted web origin `https://obrasignal.com`.
- Neon email/password sign-up is configured enabled; the ObraSignal-only `BEFORE INSERT` gate rejects users without a valid one-time invitation at database level.
- Repo invite SQLite/Neon modules do NOT prove any end-to-end invitation email delivery.
- Current frontend login remains on Supabase, pending controlled migration.

## Proposed ObraSignal email identities (not yet created or DNS-verified)
- `auth@obrasignal.com`: account activation, password recovery and security messages.
- `convites@obrasignal.com`: invitation delivery (or use auth@ as the sole transactional sender).
- `hello@obrasignal.com`: commercial enquiries.
- Keep existing `obrasignal.pt@gmail.com` operational until domain mail is proven and inbox access tested.

## No-claim checks before launch
1. Verify domain ownership, MX, SPF, DKIM and DMARC, plus receiving mailbox and ownership.
2. Configure a production transactional email provider and verify approved From identity.
3. Validate password reset/verification/registration under the managed Neon Auth provider; rate-limit and guard against email enumeration.
4. Verify invitation message routing with a controlled, user-authorized test mailbox only — no customer contact.
5. Verify *native HTTP* invited registration, signin, JWKS token, expiry, signout and recovery; SQL-only acceptance is insufficient.
6. Inventory legacy Supabase users and preserve access or obtain user approval for migration.
7. Only then switch frontend and Render JWT issuer; never switch secrets blindly.

**STATUS: not yet approved for production switch.** No claim that the listed domain mailboxes exist.
