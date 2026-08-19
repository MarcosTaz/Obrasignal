# Production E2E

The repository now has three independent production safeguards:

1. `quality.yml` runs on pull requests and pushes to `main` and executes the complete Python regression suite.
2. `production-smoke.yml` checks the live Render API health endpoint, verifies that protected API routes reject anonymous requests with `401`, validates browser CORS preflight, and checks the GitHub Pages Web shell every hour.
3. `authenticated-e2e.yml` performs a real Supabase password login and sends the returned access token to the production API. It verifies anonymous and malformed-token rejection, authenticated profile identity, account-scoped opportunities/stats/workflow stats, and detail/workflow reads when opportunity data exists.

## Required E2E secrets

The authenticated workflow intentionally does not store credentials in the repository. Configure these repository Actions secrets:

- `E2E_SUPABASE_URL` — Supabase project URL.
- `E2E_SUPABASE_PUBLISHABLE_KEY` — Supabase publishable/anon client key.
- `E2E_EMAIL` — dedicated E2E account email.
- `E2E_PASSWORD` — dedicated E2E account password.

The E2E account should be a dedicated non-human test account with a completed profile. It must not contain production customer data.

## Required production API configuration

Render must run the API in provider-authentication mode:

- `OBRASIGNAL_AUTH_MODE=provider`
- `OBRASIGNAL_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1`
- `OBRASIGNAL_JWT_AUDIENCE=authenticated`
- `OBRASIGNAL_CORS_ORIGIN=https://marcostaz.github.io`

`OBRASIGNAL_JWKS_URL` is optional; the API derives Supabase's JWKS endpoint from the issuer when omitted.

The production verifier accepts only `RS256` or `ES256` bearer JWTs and validates issuer, audience, expiry, issued-at time, subject and signing key. Anonymous and malformed bearer requests must remain `401`.

## Scope

The E2E flow is Web/API authentication coverage. Android and iOS release/build work is deliberately excluded from this gate.
