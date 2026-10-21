# Peru OECE / SEACE — evidence and source gate

## Decision

**SHARED COVERAGE / GATED**

Do not add a bespoke Peru connector and do not mark a Peru source `ready` until a permitted machine-to-machine route is proven from the ObraSignal deployment environment.

## FACT — publisher and data surfaces

- OECE publishes open contracting data through `https://contratacionesabiertas.oece.gob.pe/`.
- Current Open Contracting Kingfisher collection code (2026) uses:
  - `https://contratacionesabiertas.oece.gob.pe/api/v1/recordsAfter?format=json&order=desc`
  - opaque `searchAfter` pagination;
  - `https://contratacionesabiertas.oece.gob.pe/api/v1/files?page={page}&paginateBy=10&format=json` for bulk-file discovery.
- OECE/SEACE also exposes Plan Anual de Contrataciones (PAC), called/adjudicated procedures, contracts, suppliers and current early-signal surfaces such as future contracting announcements, expressions of interest and requirement publication.
- The publication is high-value for construction/public works and lifecycle depth.

## FACT — rights

Open Contracting's Data Registry reports the Peru publication under **CC BY 4.0**. Commercial reuse is therefore legally plausible subject to attribution and source-specific terms remaining unchanged.

## TESTED — machine access from CI

A bounded live GitHub Actions probe against the current official bulk index was executed on 2026-08-25.

Result: **HTTP 403 Forbidden** from a GitHub-hosted runner.

This is evidence of a deployment-environment/source access gate. It is not evidence that the public website is generally unavailable and it is not a reason to bypass WAF or access controls.

## DECISION — engineering

1. No scraper, browser automation, CAPTCHA handling or WAF bypass.
2. No `source_registry.py` `ready` entry while machine access is not verified.
3. When access is permitted, prefer reusable OCDS transport:
   - `recordsAfter` + `searchAfter` if the live contract proves stable incremental completeness; or
   - official bulk files if that path is operationally safer.
4. Construction admission must use publisher-native OCDS/category/classification data, not keyword-only matching.
5. PAC and other early signals should be treated as separate signal slices after transport validation.

## Reopen gate

Reopen implementation when all are true:

- official endpoint returns successful machine-readable responses from the actual deployment environment;
- pagination/completeness semantics are live-tested;
- identity and timestamps are stable enough for cursoring;
- construction taxonomy is present and validated;
- CC BY 4.0 / attribution terms remain applicable.

## Epistemic status

- RESEARCH: complete enough for classification.
- IMPLEMENTED: no production connector.
- TESTED: live access gate tested; source returned 403 from GitHub Actions.
- GATED: yes — machine access.
- MASTER QUEUE: untouched.
