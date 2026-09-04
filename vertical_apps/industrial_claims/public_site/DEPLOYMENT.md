# Supplier Recovery — isolated public-surface deployment contract

## Scope
This directory is the only Supplier Recovery public-site package. It is deliberately static, metadata-only and pre-release.

## Vercel import settings
- Repository: `MarcosTaz/Obrasignal`
- Root Directory: `vertical_apps/industrial_claims/public_site`
- Framework preset: Other / static
- Build command: none
- Output directory: `.`
- Install command: none

## Isolation requirements
- Create a new Vercel project dedicated to Supplier Recovery.
- Do not attach any Certactum, Varactum, ContractCredit or other product domain/project/runtime.
- Do not copy environment variables from another project.
- No production secrets are required for this static surface.
- Keep the generated `*.vercel.app` hostname until a Supplier Recovery domain is explicitly selected.

## Release boundary
The site remains `noindex,nofollow` and `robots.txt` blocks crawling while `data-release-gate="production-controls-pending"` is present.

This public surface may describe the product and support metadata-only discovery. It must not accept confidential contracts, POs, ECNs, drawings, invoices or ledgers. Real documentary intake requires Supplier Recovery's own verified authentication, storage, WORM/timestamp and data-handling controls.

## Promotion checks
Before any public-domain promotion:
1. exact-head repository tests are GREEN;
2. deployment package tests pass;
3. generated deployment serves `/` with HTTP 200;
4. security headers are present;
5. no cross-project identity/domain/mailbox appears in the rendered HTML;
6. no form/file-upload/document-intake surface exists;
7. custom domain selection is explicitly approved before purchase/attachment.
