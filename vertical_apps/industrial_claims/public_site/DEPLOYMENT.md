# VINDORUM — isolated public-surface deployment contract

## Scope
This directory is VINDORUM's isolated public-site package. The current release remains pre-production for confidential evidence and payment despite supporting a local, metadata-only Exposure Check.

## Vercel import settings
- Repository: `MarcosTaz/Obrasignal`
- Root Directory: `vertical_apps/industrial_claims/public_site`
- Framework preset: Other / static
- Build command: none
- Output directory: `.`
- Install command: none

## Isolation requirements
- Create a new Vercel project dedicated to VINDORUM.
- Do not attach any other product domain, project, runtime, mailbox or environment.
- Do not copy environment variables from another project.
- No production secrets are required for this static surface.
- Keep the generated `*.vercel.app` hostname until the VINDORUM domain is explicitly selected and purchased.

## Release boundary
The site remains `noindex,nofollow` and `robots.txt` blocks crawling while `data-release-gate="production-controls-pending"` is present.

The Free Exposure Check executes locally in the browser and submits nothing to a server. It must not accept file uploads. Confidential evidence requires VINDORUM's own verified authentication, case-bound storage, WORM/timestamp and data-handling controls.

## Promotion checks
Before public-domain promotion:
1. exact-head tests are GREEN;
2. the generated deployment serves `/` with HTTP 200;
3. security headers are present;
4. no cross-project identity/domain/mailbox appears;
5. no confidential file-upload surface is exposed before secure intake is verified;
6. paid Recovery Scan is not presented as live before verified billing exists;
7. custom domain selection is explicitly approved before purchase/attachment.
