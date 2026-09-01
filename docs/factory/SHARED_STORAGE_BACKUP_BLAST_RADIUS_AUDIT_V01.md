# Shared Storage & Backup Blast-Radius Audit v0.1

Status: INDEPENDENT_SAFETY_AUDIT / NON_RUNTIME / NO_MERGE_AUTHORIZATION

## Scope

Audit Factory Cloud PR #760 storage and backup primitives against the Empire Blast-Radius Rule without creating a second runtime implementation.

Observed owner implementation:
- PR #760
- branch `factory-cloud/shared-platform-portfolio-architecture`
- observed exact HEAD `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head Quality run `33265278871`: SUCCESS

Additional current Industrial Claims consumer evidence:
- PR #785
- branch `apps/industrial-claims`
- observed exact HEAD `449e3e846d1ad7096b7cf6790ecc119299a35023`
- exact-head Quality run `33270696084`: SUCCESS

## Permanent storage rule

Safe sharing means:

`SHARED IMPLEMENTATION + CONSUMER-OWNED STORAGE AUTHORITY`.

It does not mean:

`ONE DATABASE / DOCUMENT ROOT / BACKUP SET / RESTORE AUTHORITY FOR ALL COMPANIES`.

Factory Cloud's `shared_core_manifest.json` explicitly states:

`consumer-owned storage only; no cross-app production database authority`.

This audit treats that boundary as mandatory, not descriptive prose.

## AssuranceStore

Previous audit established:
- store is instantiated from an explicit database path;
- tenant-bearing records are enforced in the source/tests;
- cross-tenant collisions/reads fail closed;
- Aviation, ContractCredit and current Industrial Claims each operate from application-provided database paths.

Disposition:

`SHARED STORE IMPLEMENTATION / PER-APP STORAGE AUTHORITY REQUIRED`.

Independent approval does not extend to a single shared production SQLite/database path across unrelated products.

## DocumentStore

Factory Cloud also contains `factory_cloud/document_store.py`, a reusable raw-byte document component.

Proven source behavior:
- caller supplies an explicit root path;
- raw bytes are content-addressed by SHA-256;
- logical document ids are tenant-scoped in SQLite metadata;
- empty documents are rejected;
- a tenant/document id is immutable after first write;
- reads require tenant + document id;
- missing/corrupted object bytes fail closed;
- object writes use temp file + fsync + atomic replace.

Tests prove:
- tenant-scoped document lookup;
- same logical id may exist independently across tenants;
- cross-tenant read fails closed;
- immutable id collisions fail;
- object corruption is detected.

### Important adoption boundary

Current Aviation and ContractCredit service sources use `AssuranceStore`/`RecoveryIndex`; they do not prove direct adoption of `DocumentStore` in their service paths examined by this audit.

The Factory Cloud shared-core manifest also maps `document_ingestion_contract` to `assurance_kernel` + `assurance_store`, not to `document_store.py`.

Therefore the correct state for the raw-byte store is:

`REUSABLE SOURCE COMPONENT PROVEN / MULTI-VERTICAL RUNTIME ADOPTION NOT PROVEN`.

Do not count the existence of `DocumentStore` as G5 for document-storage promotion.

### Raw-document authority

The presence of this component refines, but does not invalidate, the earlier document-ingestion scope finding:

- a reusable raw-byte store implementation exists;
- actual acquisition, parsing, validation, malware scanning, privacy classification, retention, deletion, legal hold, encryption/key policy and application authorization remain consumer-owned;
- root-path authority must remain per application/deployment.

Industrial Claims current source separately proves product-owned intake policy, including size/evidence sufficiency and raw-content handling decisions. Those rules must not move into a generic store by convenience.

Disposition:

`RAW BYTE STORAGE IMPLEMENTATION MAY BE REUSED`
+
`DOCUMENT INTAKE/RETENTION/LEGAL AUTHORITY REMAINS APPLICATION OWNED`.

## Cross-tenant content-addressed object note

Within one `DocumentStore(root)`, identical bytes map to the same physical content-addressed object while metadata access is tenant-scoped.

This is not direct cross-tenant read authority because retrieval first resolves tenant-scoped metadata and revalidates content integrity.

However the content-addressed object layer must not be used to infer that all companies should share one production root. Physical deduplication across products would expand correlated failure, deletion, backup and forensic scope.

Independent production rule:

`ONE APP DEPLOYMENT -> ITS OWN DOCUMENT ROOT/AUTHORITY`.

Any proposal for one cross-company object root requires a fresh high-blast-radius review.

## Assurance backup / restore

`factory_cloud/assurance_backup.py` provides a low-level SQLite backup/restore utility.

Proven source behavior:
- source must exist;
- backup destination must differ from source;
- SQLite online backup API is used;
- backup integrity is checked with `PRAGMA integrity_check`;
- restored database integrity is checked;
- backup/restored file SHA-256 is recorded.

Tests prove independent round-trips for:
- Aviation;
- ContractCredit;
- Industrial Claims, including a verified RECOVERED outcome after restore.

The tests use distinct database files for each application. This is the correct containment direction.

Disposition:

`BACKUP/RESTORE UTILITY REUSE PROVEN ACROSS RECOVERY VERTICALS`
+
`OPERATIONAL BACKUP AUTHORITY REMAINS APP OWNED`.

## What backup reuse does NOT prove

The low-level utility does not itself define or authorize:
- production backup schedules;
- retention periods;
- off-site replication;
- encryption-at-rest or key ownership;
- backup bucket/container sharing;
- backup access-control roles;
- legal hold/deletion policy;
- disaster-recovery RTO/RPO;
- multi-region strategy;
- restore approval authority;
- customer-data export authority;
- one global restore operation across products.

These remain per-product/deployment concerns unless separately proven and approved.

## Promotion consequence

`backup_recovery_contracts` appears as a shared-platform candidate in portfolio planning but is not presently promoted as a `SHARED_VERIFIED`/`SHARED_CORE` capability in `capability_inventory.json`.

That conservative state is correct.

Before promotion, require at minimum:
1. explicit contract separating library behavior from operational authority;
2. at least two application consumers with distinct storage paths;
3. restore tests at exact heads;
4. evidence that one application's restore cannot overwrite another application's data path;
5. explicit ownership of encryption/retention/backup destination per app;
6. rollback/recovery runbook proving independent containment.

## Portfolio/UI audit note

Factory Cloud's architecture snapshot labels its authority as planning/switchboard metadata only and explicitly sets:
- no repository-write grant;
- no production-write grant;
- no cross-app data-access grant;
- no merge grant.

The capability inventory is exposed as structured planning evidence rather than a customer-facing entitlement engine.

The legacy Switchboard UI inherited by PR #760 is not changed by PR #760. The dedicated Control Tower owner PR #722 already replaces the old manual/clipboard-only behavior with API dispatch, uses the canonical `D` command, and states runtime truth separately from routing truth.

Composition requirement:

**Do not integrate PR #760 in a way that overwrites or regresses PR #722's canonical D/API-dispatch Switchboard.**

## Findings

No new shared-storage runtime defect requiring a PR #760 implementation change was proven in this audit.

Material constraints remain:
- per-app storage authority is mandatory;
- raw `DocumentStore` multi-vertical adoption is not proven;
- backup operational authority is not shared;
- source-verification worker integration defect remains separately open;
- capability labels must stay narrower than their proven semantics.

## ACTIVE / NEXT / WAIT

ACTIVE: preserve per-app storage/backup authority and re-audit composition whenever Factory Cloud shared implementation or Control Tower branches move.

NEXT: verify PR #760 / #722 composition does not regress canonical D/API dispatch or source-verification safety; then re-check exact-head CI and owner repair state.

WAIT: shared production databases, shared raw-document roots across products, shared backup credentials/buckets, cross-product restore authority, merge and deploy remain outside this Side Factory's authority.
