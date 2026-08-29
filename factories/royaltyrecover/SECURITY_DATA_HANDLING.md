# RoyaltyRecover — Assisted Pilot Security & Data-Handling Boundary

Date: 2026-08-29
Status: REQUIRED PILOT CONTROL — NOT A SECURITY CERTIFICATION

## Security objective

RoyaltyRecover handles commercially sensitive licensing economics. The assisted pilot must minimize retained confidential content while preserving enough immutable lineage to reproduce calculations and reviews.

## Data classes

### A — Highly sensitive source content
Examples:
- full license agreements and amendments;
- royalty statements containing confidential sales detail;
- transaction-level sales/usage files;
- bank/payment documents;
- formal auditor workpapers or findings.

Default pilot rule:
**Do not persist raw Class A content inside the minimum RoyaltyRecover SQLite application.**

The current minimum text endpoints hash supplied content for lineage and discard the raw body. The source original must remain in a customer-approved document system or other separately approved secure store.

### B — Derived contractual/economic records
Examples:
- agreement/version identifiers;
- document SHA-256;
- short reviewed clause excerpt;
- deterministic royalty rule;
- evidence identifier/type/hash;
- calculation input hash and engine version;
- analytical candidate amount;
- review state/rationale;
- external outcome state;
- verified-payment state.

These are persisted by the assisted pilot because they are required for reproducibility and auditability. They remain confidential customer data.

### C — Operational metadata
Examples:
- tenant identifier;
- actor/key identifier;
- role;
- audit-event timestamp;
- deployment commit;
- backup hash;
- operational timings/unit-economics measurements.

Persist only what is needed for security, auditability and pilot economics.

## Tenant boundary

Every application credential is bound to one organization.

Controls already implemented:
- tenant-scoped repository reads/writes;
- cross-tenant object lookups return not found;
- duplicate credential secrets across tenants are rejected at configuration time;
- reviewer capability requires separate role authorization;
- formal-audit packet and recovery register are tenant-scoped;
- verified-recovery summaries are tenant-scoped.

Do not create global operator endpoints that enumerate customer data across tenants in the assisted build.

## Credential handling

- secrets only in deployment secret/environment configuration;
- never in repository, issue, PR, screenshot, support ticket or audit-event payload;
- unique secret per credential;
- separate analyst/reviewer credentials;
- rotate immediately on suspected exposure;
- remove former staff/contractor credentials promptly;
- static API credentials are an assisted-pilot control, not the intended production identity architecture.

## Human review separation

An analyst may:
- create tenant-scoped entities/evidence hashes;
- prepare unreviewed clauses/rules;
- run allowed analysis only after review gates are satisfied;
- record evidence-backed payments.

A reviewer is required to:
- approve/reject source clauses;
- approve/reject deterministic royalty rules;
- approve/reject/route persisted findings;
- record recovery-bearing outcomes;
- create and verify recovered-amount records.

No API input may directly create a clause/rule as reviewed.

## Recovery integrity

A monetary state must progress separately through:

`ANALYTICAL CANDIDATE`
→ external review/audit/settlement evidence
→ `RECOVERY OUTCOME`
→ payment evidence
→ `UNVERIFIED RECOVERED AMOUNT`
→ explicit reviewer verification
→ `VERIFIED_PAYMENT`.

The user-supplied `recoverable_candidate` field is ignored by the deterministic persisted scan path; the engine derives the candidate from reviewed rules and source inputs.

A recovered amount cannot exceed the evidenced payment used to support it.

## Backup security

Backups contain confidential Class B/C data and must receive the same or stronger access controls as the live database.

Required controls:
- timestamped/non-overwriting filenames;
- SHA-256 recorded independently;
- SQLite integrity check;
- periodic restore drill to a separate environment;
- no backup copied to public object storage or source control;
- delete only under the customer's agreed retention policy.

## Logging

Application/audit records should contain identifiers and state transitions, not raw agreement text, raw statement content, API secrets or bank-document content.

Reverse-proxy/access logging must not be configured to capture authentication headers.

## Network/runtime boundary

For an external assisted pilot:
- HTTPS is mandatory;
- persistent database volume is mandatory;
- public debug mode is prohibited;
- SQLite build runs as a single application instance;
- container runs as a non-root user;
- `/api/v1/readiness` is authenticated;
- `/health` contains no tenant or database detail.

## Retention/deletion

No universal retention period is invented by the product.

Before real client onboarding, the engagement must define:
- retention period for derived records;
- backup retention;
- what happens at engagement end;
- whether the customer requires legal hold;
- where source originals remain;
- deletion/return process;
- whether audit-event history must be retained separately.

Until those terms exist, do not claim GDPR/SOC 2/ISO 27001 or customer-policy compliance.

## Security gates still open before production

The assisted pilot does not yet provide:
- enterprise SSO/MFA;
- managed secrets lifecycle/rotation UI;
- managed database HA/PITR;
- centralized security logging/SIEM;
- formal penetration test;
- vulnerability-management SLA;
- DPA/security questionnaire package;
- documented subprocessor inventory for a real hosting environment;
- SOC 2 / ISO 27001 certification.

Those are production/security-readiness dependencies, not reasons to mislabel the current controlled pilot as production-ready.
