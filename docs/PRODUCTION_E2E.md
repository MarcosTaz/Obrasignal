# Production E2E

The repository now has three independent production safeguards:

1. `quality.yml` runs on pull requests and pushes to `main` and executes the complete Python regression suite.
2. `production-smoke.yml` checks the live Render API health endpoint, verifies that protected API routes reject anonymous requests with `401`, validates the browser CORS preflight, and checks the GitHub Pages Web shell every hour.
3. `authenticated-e2e.yml` performs a real Supabase password login and sends the returned access token to the production API. It then verifies authenticated profile identity and opportunity access.

## Required E2E secrets

The authenticated workflow intentionally does not store credentials in the repository. Configure these repository Actions secrets:

- `E2E_SUPABASE_URL`
- `E2E_SUPABASE_PUBLISHABLE_KEY`
- `E2E_EMAIL`
- `E2E_PASSWORD`

The E2E account should be a dedicated non-human test account with a completed profile. It must not contain production customer data.

## Scope

The E2E flow is Web/API authentication coverage. Android and iOS release/build work is deliberately excluded from this gate.
