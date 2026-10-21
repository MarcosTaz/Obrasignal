# Opportunity Document Inventory / Bid Document Pack v0

**Capability state:** PILOT contract, not production-integrated  
**Contract:** `document_inventory.v0`  
**Scope:** public/shared procurement-document metadata only

## PURPOSE

ObraSignal needs to answer a bounded question for an opportunity: **which official document references are known, which are current or explicitly superseded, what is available, and what still needs verification?**

The capability turns source document references into a stable, auditable inventory. A document reference is not treated as proof that bytes are available, accessible, parsed, current, legally reusable, or required for submission.

## NON-GOALS

V0 is not a document-management system, file-storage service, PDF editor, collaboration suite, bid generator, submission engine, OCR stack, translation service, malware scanner, BOQ extractor or drawing interpreter. It does not download document bytes while building or listing the inventory.

Company uploads and tenant-private documents are explicitly outside V0. ACTION, Requirements, Readiness, Evidence Graph, Supply Edge and alert generation remain separate capabilities.

## CURRENT REPOSITORY STATE

At implementation time the repository uses a modular-monolith architecture and a canonical `tenders` opportunity projection with SQLite sidecars keyed by source identity. No existing canonical opportunity-document inventory or file-storage subsystem was identified in the inspected repository tree and relevant source/API models. V0 therefore introduces a document metadata sidecar without modifying the opportunity source-of-truth.

The canonical Master Execution Queue remains unchanged. This parallel module does not modify `CURRENT_ITEM_ID`, reorder queue items or promote ACTION/Supply/Requirements work.

## DOCUMENT MODEL

`OpportunityDocument` contains only metadata useful to identity, classification, availability, provenance and version relationships:

- stable `document_id`;
- opportunity source identity (`opportunity_source`, `opportunity_external_id`);
- document source and optional native `external_id`;
- title;
- document type and classification basis;
- purpose and explicit required-for-submission state;
- document status and separate availability status;
- source reference / validated external URL / publisher;
- published, updated and effective timestamps when supplied;
- MIME type, language and optional file size;
- source-provided version;
- content or metadata fingerprint with explicit fingerprint kind;
- optional native package reference and parsed flag;
- simple document relationships;
- bounded raw source metadata.

V0 stores **metadata only**, never document bytes.

## TYPE SYSTEM

Supported document types are:

`NOTICE`, `SPECIFICATION`, `TECHNICAL_SPECIFICATION`, `BOQ`, `DRAWING`, `PRICING_SCHEDULE`, `QUALIFICATION_FORM`, `DECLARATION`, `CONTRACT_DRAFT`, `CLARIFICATION`, `AMENDMENT`, `CORRIGENDUM`, `APPENDIX`, `SUBMISSION_TEMPLATE`, `OTHER`, `UNKNOWN`.

`UNKNOWN` is a first-class outcome. Source-provided valid classifications have basis `SOURCE`. Conservative deterministic title/filename rules have basis `INFERRED`. V0 intentionally has no ML classifier.

False-positive protection prevents generic guidance/examples/manual-like names from becoming authoritative BOQs or other official types merely because they contain a keyword.

## PURPOSE AND REQUIRED-FOR-SUBMISSION

Purpose is independent of type and supports:

`FOR_INFORMATION`, `FOR_ANALYSIS`, `FOR_QUALIFICATION`, `FOR_PRICING`, `FOR_SUBMISSION`, `FOR_CONTRACT`, `UNKNOWN`.

`required_for_submission` is `REQUIRED`, `NOT_REQUIRED` or `UNKNOWN`. A submission form, pricing schedule or other likely bid document is **not** marked `REQUIRED` unless the source/reference supplies explicit evidence. The inventory reports what exists; a Requirements capability decides what an opportunity actually requires.

## STATUS VS AVAILABILITY

Document lifecycle status:

- `CURRENT`
- `SUPERSEDED`
- `WITHDRAWN`
- `UNKNOWN`

Availability:

- `AVAILABLE`
- `REFERENCE_ONLY`
- `UNAVAILABLE`
- `ACCESS_RESTRICTED`
- `MISSING`
- `UNKNOWN`

They are deliberately orthogonal. For example, a document may be `CURRENT` and `ACCESS_RESTRICTED`.

A failed or restricted reference is retained rather than silently deleted. V0 does not turn a network timeout into `MISSING`; source adapters must supply the defensible availability state.

## IDENTITY

URL is not identity. The stable document ID is derived from opportunity identity plus the strongest defensible document identity available:

1. explicit content fingerprint when the caller actually has bytes/content identity;
2. source/native document identifier plus explicit version;
3. deterministic metadata fingerprint when no stronger identity exists.

A metadata fingerprint is explicitly labelled `METADATA` and must never be represented as proof that two byte streams are identical.

Different URLs can therefore resolve to one logical document version. Conversely, the same native name/id with a different content hash can represent distinct versions.

## DEDUPLICATION AND IDEMPOTENCY

Normalization is order-independent. Repeated identical references collapse to one stable `document_id`; persistence uses an upsert keyed by that ID. Reprocessing the same set updates observation metadata without duplicating logical documents.

Source list disappearance is not interpreted as withdrawal. Only explicit status/relationship evidence changes lifecycle semantics.

## VERSIONING AND SUPERSESSION

V0 preserves source-provided version strings but never invents official version numbers.

Supersession is applied only when the input explicitly identifies a target via stable document ID or an unambiguous source-native target identifier. Both versions remain stored. The old document becomes `SUPERSEDED`; the new one carries a `SUPERSEDES` relationship.

If two similarly named versions exist but the source does not provide defensible linkage, V0 leaves them unresolved and exposes them through `needs_verification` when lifecycle/availability/requirement dimensions remain unknown. It does not arbitrarily choose a winner.

An `AMENDMENT` is a document type, not an assumption that a complete document pack was replaced. Supported relationship types are `SUPERSEDES`, `AMENDS`, `APPENDS_TO` and `RELATED_TO`.

## SOURCE PROVENANCE

The inventory preserves source, publisher when supplied, source reference, native identifier and source-provided timestamps. Raw source metadata is retained in a bounded JSON field for traceability.

The capability does not duplicate or reinterpret legal/reuse policy. Accessibility is not treated as a commercial reuse licence.

## PERSISTENCE

`ensure_document_tables(conn)` idempotently creates two SQLite structures in the existing database:

- `opportunity_documents` — public/shared document metadata;
- `opportunity_document_relationships` — simple explicit relations.

There is no separate database or file store. No `account_id`/`tenant_id` is introduced because V0 contains only public opportunity documents. Future company-uploaded documents require a separate tenant-private contract and authorization boundary.

The tables are sidecars keyed to opportunity source identity; they do not mutate or duplicate the `tenders` source-of-truth.

## READ MODEL / API

`get_document_inventory(conn, opportunity_source, opportunity_external_id)` is the V0 read contract. It returns:

- `current_documents`;
- `superseded_documents`;
- `missing_or_unavailable`;
- `unknown_documents`;
- `submission_related`;
- `analysis_related`;
- `needs_verification`;
- generation timestamp and inventory contract version.

A public HTTP route is deliberately **not wired in V0**. No inspected production source adapter currently emits the canonical document-reference contract, so exposing an endpoint now would create an apparently integrated but systematically empty product surface. The next safe integration step is to map one official source's native document metadata into this contract, prove it with fixtures/live evidence appropriate to that source, then expose `GET /api/v1/opportunities/{id}/documents` using existing auth/API conventions.

## UI

No UI is added in V0 for the same reason: there is no production document-producing connector yet. The intended future presentation is contextual inside opportunity detail, separating current, updated/amended, superseded and unavailable references without mirroring internal capability architecture.

## SECURITY

- External URLs are untrusted input. Only absolute `http`/`https` URLs without embedded credentials are exposed as clickable source URLs.
- Unsafe schemes and schemeless values are rejected; an unsafe URL cannot remain `AVAILABLE` merely because input asserted it.
- Titles/filenames are data only. They are never executed or used as filesystem paths.
- V0 never opens macros, executes files, extracts ZIPs or materializes documents.
- Raw metadata is size-bounded to prevent unbounded payload persistence.
- File size, MIME type and classification are only preserved when known; no download is performed to discover them.
- Future stored downloads must add malware scanning and content-security controls before production use.
- Public/shared document metadata contains no company tenant data.

Presentation layers must continue to use framework escaping for titles and labels. This module does not emit HTML.

## TESTS

The dedicated test suite covers:

- single and multiple documents;
- deterministic type classification and `UNKNOWN`;
- BOQ / technical specification / pricing schedule / contract draft / clarification / amendment;
- false-positive BOQ guidance;
- source classification precedence;
- duplicate native references;
- same filename/native identity with different content hashes;
- bytes-only content hashing;
- explicit supersession and preservation of history;
- unknown-version non-guessing;
- amendment non-replacement semantics;
- unavailable and access-restricted references;
- missing provenance failure;
- URL scheme/credential safety;
- hostile title handling;
- oversized metadata and invalid size rejection;
- order-independent normalization;
- repeated-ingestion idempotency;
- raw metadata preservation;
- public/shared schema semantics;
- no-download inventory listing;
- no mutation of opportunity source state;
- separation of lifecycle, availability, purpose and submission requirement.

## LIMITATIONS

- No official source adapter emits this contract yet; source integration is future work.
- No HTTP/UI production wiring is claimed.
- No content fetch means content fingerprints are only accepted when supplied by an upstream process that genuinely had bytes.
- Native source version semantics differ; V0 preserves supplied values rather than pretending they are globally comparable.
- Metadata-only identity can be conservative and may require source-specific strengthening.
- No automatic removal/withdrawal is inferred from an incomplete source snapshot.

## FUTURE INTEGRATIONS

Safe future consumers include Requirements, Change History, Readiness, Evidence Graph, Supply Edge and bid preparation. They must consume this explicit contract rather than reading private persistence directly.

Potential future events such as document-added/replaced should be emitted only after source ingestion semantics and replay/idempotency are proven. Alerting, parsing, OCR, summarisation, translation, BOQ extraction, redlining, proposal generation, customer uploads and submission automation remain out of scope.

## ROLLBACK

The capability is isolated. Rollback consists of removing its module/tests/docs and, if desired, leaving the additive SQLite tables unused. The migration is non-destructive and does not alter `tenders` or the canonical Master Execution Queue.

## NEXT SAFE STEP

Integrate exactly one official source that exposes defensible document metadata, map native identifiers/types/version/amendment relationships conservatively, validate idempotency and provenance, then wire the authenticated read-only API and opportunity-detail UI behind existing rollout conventions.
