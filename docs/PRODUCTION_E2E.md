# Production E2E

The repository has three independent production safeguards:

1. `quality.yml` runs on pull requests and pushes to `main` and executes the complete Python regression suite.
2. `production-smoke.yml` checks the live Render API health endpoint, verifies that protected API routes reject anonymous requests with `401`, validates browser CORS preflight, and checks the GitHub Pages Web shell every hour.
3. `authenticated-e2e.yml` performs a real Supabase password login and sends the returned access token to the production API. It verifies anonymous and malformed-token rejection, authenticated profile identity, account-scoped opportunities/stats/workflow stats, and detail/workflow reads when opportunity data exists.

## Required E2E secrets

The authenticated workflow intentionally does not store credentials in the repository. Configure these repository Actions secrets:

- `EXPO_PUBLIC_SUPABASE_URL` — Supabase project URL used by the application/E2E workflow.
- `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` — Supabase publishable client key.
- `E2E_EMAIL` — dedicated E2E account email.
- `E2E_PASSWORD` — dedicated E2E account password.

The E2E account should be a dedicated non-human test account with a completed profile. It must not contain production customer data.

## Required production API configuration

Render must run the API in provider-authentication mode:

- `OBRASIGNAL_AUTH_MODE=provider`
- `OBRASIGNAL_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1`
- `OBRASIGNAL_JWT_AUDIENCE=authenticated`
- `OBRASIGNAL_CORS_ORIGIN=https://marcostaz.github.io`

For a native `*.supabase.co` project the verifier canonicalizes equivalent project URLs such as the project root or `/rest/v1` to `/auth/v1`. Native Supabase JWKS discovery is always derived from that canonical issuer, so a stale `OBRASIGNAL_JWKS_URL` cannot override the provider's current public signing-key endpoint. Explicit JWKS overrides remain supported only for non-Supabase OIDC-compatible issuers.

The production verifier accepts only `RS256` or `ES256` bearer JWTs and validates issuer, audience, expiry, issued-at time, subject and signing key. The token algorithm must match the selected JWK algorithm. Anonymous and malformed bearer requests must remain `401`; JWKS transport failure remains a controlled `503`.

## Verification policy

A green pull-request run is not sufficient to claim production verification. The `main` branch must produce a fresh run for the quality, production-smoke, and authenticated-E2E workflows after changes land. Production E2E is considered verified only when the authenticated workflow completes successfully with the configured repository secrets.

If Supabase authentication succeeds and the safe workflow diagnostics show a supported algorithm, matching `kid`, matching issuer and `authenticated` audience, but the production API still returns `401`, check the Render `OBRASIGNAL_JWT_ISSUER` project host. The application intentionally does not trust an unverified token to choose its issuer, because doing so would allow tokens issued by an unrelated Supabase project.

## Scope

The E2E flow is Web/API authentication coverage. Android and iOS release/build work is deliberately excluded from this gate.
