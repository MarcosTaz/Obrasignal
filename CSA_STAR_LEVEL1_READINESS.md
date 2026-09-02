# ObraSignal — CSA STAR Level 1 readiness register

Status: **PREPARATION / NOT YET CSA STAR CERTIFIED**

This document is the internal evidence register for a future CSA STAR Level 1 self-assessment submission. It must not be used to claim certification before the Cloud Security Alliance registry accepts/publishes the submission.

## Current evidence already present

- Authenticated production checks exist in GitHub Actions.
- Account privacy production checks exist, including export/delete contract coverage.
- Browser E2E coverage exists across Chromium, Firefox and WebKit.
- Production smoke checks cover deployed Web/API boundaries.
- Push acceptance checks exercise authenticated server/preference contracts.
- Canonical origin/CORS hardening is implemented.
- Public Privacy, Terms and Support surfaces are present.
- Tenant-scoped private storage binding is implemented in the client.
- A live second-tenant isolation proof remains an external completion item and must not be represented as complete until the provider/account block is resolved.

## Public claim policy

Allowed now:

- HTTPS / TLS on the published Web service where the serving endpoint is HTTPS.
- Privacy controls available.
- Authenticated production testing performed.
- Browser E2E testing performed.
- “CSA STAR Level 1 self-assessment in preparation — not yet certified.”

Not allowed until external proof exists:

- “CSA STAR certified”, “CSA STAR registered” or use of a CSA certification/registry badge as if granted.
- “ISO 27001 certified”.
- “SOC 2 certified/compliant”.
- “GDPR certified”.
- “CyberSecure Canada certified”.
- Any regulator/government seal not explicitly granted to ObraSignal.

## Submission workstream

1. Obtain the current CSA CAIQ/CCM submission template from the Cloud Security Alliance.
2. Map each applicable control to repository, production and policy evidence.
3. Mark unsupported controls as NO or N/A with rationale; never infer a YES from intent.
4. Resolve material gaps before submission where feasible.
5. Complete organization/service identity fields.
6. Owner reviews legal declarations and authorizes final submission.
7. Submit through the official CSA STAR organization submission route.
8. Only after official registry publication, update the public trust bar from “in preparation” to the exact granted/registered status and link to the official registry entry.

## Free-trust roadmap after STAR Level 1

- Keep HTTPS/TLS certificate automation enabled on the canonical domain after DNS activation.
- Apply for Portuguese SME certification only when the legal entity is eligible.
- Evaluate free governmental/security self-assessments in target markets, but display only marks for which ObraSignal is demonstrably eligible and approved.

## Evidence integrity rule

Every public trust mark must have all four of the following:

1. issuer or technical authority;
2. exact status/level;
3. evidence URL or internal immutable proof;
4. date/status validity.

If any element is missing, the UI must describe the item as a capability, test, preparation state or pending application — never as a certification.
