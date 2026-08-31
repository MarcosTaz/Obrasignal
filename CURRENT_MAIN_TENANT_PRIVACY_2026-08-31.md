# Current-main tenant privacy closure — 2026-08-31

Base: `main` at `c85a0b9211eff9a81af3ed5fae4b5bea80c0ac68`.

This composition preserves the newer authenticated web/billing work on main and applies the mobile private-storage repair directly on top of it.

Acceptance contract:
- authenticated private cache/settings/profile are keyed by Supabase `session.user.id`;
- AuthGate does not render the private application shell before storage binding succeeds;
- account switch purges the previously active account's private device cache;
- sign-out purges the active account's private device cache;
- legacy global v1 private keys are purged and never hydrated;
- cache envelopes are identity checked before hydration;
- storage-binding transitions are serialized to prevent A/B auth-event races;
- dynamic A→B→logout regression executes inside `npm run smoke:detail`, which is part of ObraSignal Quality CI.

Promotion rule: only promote after the exact branch head passes Python and mobile quality jobs. No stale company-truth branch should overwrite newer main work.
