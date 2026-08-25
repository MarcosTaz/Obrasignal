# Production E2E

Production authentication is protected by distinct gates with non-overlapping responsibilities:

1. `quality.yml` — unit/regression quality. It runs on pull requests and pushes to `main`, including Python compilation/tests and the repository's mobile/detail smoke gates.
2. `auth-verifier-live.yml` — real Supabase JWT verifier gate. It logs into the configured dedicated E2E account, obtains the provider's current access token/JWKS, and verifies that token through the exact branch `JwtVerifier`. It does not call the deployed API and therefore is not production E2E.
3. `production-smoke.yml` — deployed production smoke. The live Render `/api/v1/health` response must identify the exact `github.sha` under test before anonymous boundary, CORS, and GitHub Pages shell checks are accepted.
4. `authenticated-e2e.yml` — full authenticated deployed API gate. It waits for the exact `github.sha` to be reported by production, performs real Supabase login, verifies anonymous/malformed-token rejection, authenticated profile identity and persistence, account-scoped opportunities/stats/workflow stats, and detail/workflow reads when data exists.
5. `auth-diagnostic.yml` — manual diagnostic only. It checks required secret presence without printing secret values or password-derived fingerprints, probes Supabase Auth settings, authenticates the dedicated `E2E_EMAIL`, and validates the public JWKS shape. It is not a release gate.

The former `authenticated-e2e-app-credentials-probe.yml` was removed because it duplicated the login portion of the authenticated E2E and sent the Supabase publishable key as a bearer token. The canonical login request is API-key-only (`apikey` header) plus the dedicated account credentials.

## Required E2E secrets

The authenticated workflows intentionally do not store credentials in the repository. Configure these repository Actions secrets:

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

For a native `*.supabase.co` project the verifier canonicalizes equivalent project URLs such as the project root, `/rest/v1`, `/auth/v1`, or an obsolete Supabase path to the trusted project host plus `/auth/v1`. Native Supabase JWKS discovery is always derived from that canonical issuer, so a stale `OBRASIGNAL_JWKS_URL` cannot override the provider's current public signing-key endpoint. Explicit JWKS overrides remain supported only for non-Supabase OIDC-compatible issuers.

The production verifier accepts only `RS256` or `ES256` bearer JWTs and validates signature, `kid`, algorithm/JWK agreement, issuer, audience, expiry, issued-at time, and subject. Tokens from another Supabase project remain invalid because provider selection never trusts an unverified token. Anonymous, malformed, wrong-issuer, wrong-audience, expired, future-invalid, unknown-key, and unsupported-algorithm inputs fail closed. JWKS transport/provider unavailability remains a controlled `503`, with bounded stale-key and refresh behavior.

Runtime authentication logs emit bounded reason categories only (for example issuer mismatch, audience mismatch, unknown key, malformed/expired token, or JWKS unavailable). They do not log JWTs, passwords, signing material, credentials, or environment dumps. The public API response remains intentionally coarse (`401 authentication_required` or controlled `503 authentication_service_unavailable`).

## Deployment provenance

`/api/v1/health` returns the deployed build identifier from `OBRASIGNAL_BUILD` or Render's `RENDER_GIT_COMMIT`. Both `production-smoke.yml` and `authenticated-e2e.yml` require that value to equal the workflow's `github.sha` before their production assertions count. A green branch or a healthy older Render revision is therefore insufficient to claim production validation.

## Verification policy

A green pull-request run is not sufficient to claim production verification. After controlled merge/deploy, the same deployed `main` revision must produce fresh green results for quality, production smoke, and authenticated E2E. The JWT live gate proves the real current Supabase token shape independently of the deployed API.

If real Supabase login/JWKS verification succeeds but the deployed API still returns `401`, inspect the bounded server-side auth reason and Render's trusted `OBRASIGNAL_JWT_ISSUER` project host. The application intentionally does not infer or replace the trusted issuer from an unverified token.

## Tenant identity

Verified JWT `sub` is the server-side account identity. Client-supplied `account_id` values in payloads do not override it, and account-scoped reads use the verified identity. Regression tests cover account separation and request-identity precedence. The single-account production E2E verifies consistent account scoping for the dedicated E2E identity; a true live A-vs-B production isolation exercise requires two dedicated E2E identities and must not be claimed unless both credentials are explicitly configured.

## Scope

The E2E flow is Web/API authentication coverage. Android and iOS release/build work is deliberately excluded from this authentication gate.
