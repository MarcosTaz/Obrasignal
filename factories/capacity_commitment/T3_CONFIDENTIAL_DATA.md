# Capacity Commitment — T3 Confidential Buyer-Data Handling

Status: **READY FOR FIRST REAL DATA HANDOFF**

Purpose: prevent a real buyer case from leaking into public development surfaces or being mixed with another Factory/company while preserving enough source identity for auditability.

This is an operational control, not a legal privacy opinion or substitute for customer-specific contractual/data-protection review.

## Hard boundary

Real proprietary buyer/customer/programme material must **not** be placed in:

- public GitHub repositories, issues, pull requests or comments;
- public web search/query text;
- public examples, synthetic fixtures or screenshots;
- another Factory/company workspace;
- model-training datasets without explicit permission;
- email to a new recipient not authorized by the buyer;
- logs or debugging output intended for public/support sharing.

Public GitHub may contain only synthetic/redacted structures that cannot disclose the real customer case.

## Before receiving data

Confirm:

1. supplier legal entity / tenant;
2. buyer/champion and role;
3. one bounded customer/programme/period;
4. authorized transfer route;
5. intended purpose: Capacity Commitment eligibility/pilot only;
6. known confidentiality/NDA/DPA requirements;
7. whether third-party/customer documents may legally be shared with us;
8. whether any special-category, personal, export-controlled or legally privileged material is expected.

If authorization is unclear, request a bounded non-sensitive outline first rather than accepting a broad data dump.

## Data-minimisation order

Prefer, in order:

1. anonymized programme outline;
2. redacted relevant clauses/extracts;
3. bounded rows/period from releases/shipments/amortisation;
4. only then full relevant source documents if necessary and authorized.

Do not ask for an entire ERP export, customer portfolio or legal data room when one programme extract is enough.

## Source identity without public disclosure

For each real source preserve privately:

- source ID;
- original filename/title;
- version/effective date;
- document type;
- customer/programme identity;
- supplied-by identity;
- received timestamp;
- checksum/content identity where available;
- redaction/incompleteness note;
- amendment/supersession relationship.

Public Factory records may state only a non-sensitive truth such as `DATA_PROVIDED=YES`, source count, or a synthetic/internal reference if doing so does not reveal confidential facts.

## Processing rules

- unknown stays unknown;
- do not infer missing contract language from commercial expectations;
- do not merge similarly named programmes/customers without explicit identity proof;
- preserve currency/unit/period boundaries;
- do not overwrite a source version invisibly;
- do not copy buyer data into sister-company Factories;
- do not expose the report externally until authorized human review;
- do not use proprietary data to improve/train models without explicit permission.

## Redaction rule for external deliverable

Before sharing a generated findings report outside the authorized buyer group:

- verify intended recipient;
- verify customer/programme identifiers may be shown;
- remove irrelevant personal contact data;
- ensure source references do not expose file-system paths, internal secrets or unrelated customer names;
- ensure no internal Factory controls/HOLD labels appear;
- preserve the report truth boundary (`verified_recovery=false`, `payment_received=false` unless separately evidenced).

## Retention / deletion state

Until a real customer agreement specifies retention/deletion requirements, do **not** promise a specific retention period.

For every real pilot record:

- agreed retention rule: `UNKNOWN` until established;
- deletion request status;
- legal/contractual hold status if any;
- backup implications;
- completion/deletion evidence when applicable.

Do not claim deletion if copies remain in backups or other authorized stores.

## Incident response

If proprietary data is accidentally placed in a public or wrong-tenant surface:

1. stop further propagation;
2. treat containment as ACTIVE P0;
3. remove/restrict exposed material through the appropriate authorized system;
4. preserve enough internal incident evidence to understand scope without re-publishing the data;
5. identify affected tenant/customer/source;
6. escalate any required legal/customer notification rather than inventing obligations;
7. resume normal T3 execution only after containment and integrity review.

## First-case gate

Before accepting the first proprietary dataset, confirm all of:

- authorized transfer route exists;
- case identity is frozen;
- bounded purpose is stated;
- public-repo exclusion is understood;
- minimum data request is used;
- recipient/review path is known;
- retention/legal terms that are required before processing are either satisfied or explicitly escalated.
