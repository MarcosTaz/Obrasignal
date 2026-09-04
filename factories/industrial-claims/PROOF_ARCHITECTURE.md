# CausLedger — Maximum-Strength Evidence & Proof Architecture

Status: ACTIVE PRODUCT CONTRACT

## Objective

CausLedger must not merely keep an audit trail. It must be able to produce a self-contained, independently verifiable proof package showing, as far as the available evidence supports it:

- what was received;
- where it came from;
- when CausLedger first saw it;
- what the original digest was;
- whether it changed;
- who created/reviewed/acknowledged it;
- what version superseded what;
- what evidence supports or contradicts the commercial narrative;
- what calculation and ruleset produced the economic result;
- which assertions are independently attested by external trust providers;
- which proof gates remain unproven.

Cryptographic integrity MUST NEVER be presented as proof that a factual statement is true, that a customer is responsible, or that money is legally recoverable.

## Core proof objects implemented in the repository

### 1. CausLedger Proof Pack

`vertical_apps/industrial_claims/proof_package.py`

Wraps the current durable claim package without changing its documentary/economic truth. The Proof Pack contains:

- unchanged `core_package`;
- `proof_manifest`;
- explicit proof-strength gates;
- internal self-verification result;
- explicit flag when external verification gates remain unsatisfied.

### 2. Proof manifest and verification core

`vertical_apps/industrial_claims/proof.py`

Implemented:

- canonical JSON serialization;
- SHA-256 package digest;
- SHA-512 package digest;
- evidence SHA-256 validation;
- optional evidence SHA-512 lineage;
- domain-separated SHA-256 Merkle root;
- evidence assurance state machine;
- external-attestation model;
- fail-closed external proof gates;
- stable external attestation target that excludes the attestation receipts themselves and therefore avoids recursive/self-changing signature targets;
- rejection of a VERIFIED external attestation if its digest does not match the stable target;
- manifest SHA-256 and SHA-512;
- independent package/Merkle/target/manifest verification;
- truth-boundary declarations.

Evidence states are strictly progressive and cannot be upgraded merely because a hash exists:

`UNVERIFIED -> SOURCE_AUTHENTICATED -> INTEGRITY_SEALED -> TIME_SEALED -> CORROBORATED -> HUMAN_REVIEWED -> COUNTERPARTY_ACKNOWLEDGED -> QUALIFIED_SEALED`

### 3. Append-only proof ledger

`vertical_apps/industrial_claims/proof_store.py`

Implemented:

- server first-seen time distinct from declared effective time;
- explicit anti-backdating model;
- append-only event ledger;
- per-case SHA-256 hash chaining;
- deterministic payload digest;
- chain verification;
- immutable external attestation registry;
- immutable proof certificate registry;
- immutable supersession registry;
- SQLite triggers rejecting UPDATE/DELETE of proof records;
- tenant scoping;
- certificate issuance blocked if the chain fails verification.

Application-level append-only storage is NOT described as WORM. External WORM remains a separate gate.

### 4. External trust-provider interfaces

`vertical_apps/industrial_claims/proof_providers.py`

Interfaces are present for:

- qualified electronic timestamp;
- qualified electronic seal;
- qualified electronic signature;
- WORM/Object Lock receipt;
- public/transparency-log anchor;
- evidence escrow.

The default provider bundle is deliberately `UNAVAILABLE`/fail-closed. No external service is considered valid until a real provider returns a verifiable provider reference/receipt.

### 5. Offline verifier

`vertical_apps/industrial_claims/proof_verifier.py`

A third party can verify a JSON Proof Pack without relying on the CausLedger web application for package/Merkle/attestation-target/manifest integrity. External qualified signatures/timestamps require the corresponding trust-chain validation material/provider verification path.

### 6. Evidence certificates and forensic extensions

`vertical_apps/industrial_claims/proof_extensions.py`

Implemented building blocks:

- dual SHA-256/SHA-512 digest at capture time;
- deterministic textual semantic-diff payload explicitly marked unsigned until a real external signature/seal is attached;
- causal graph with evidence on every edge;
- adverse/contradictory evidence register;
- calculation provenance;
- software/build/ruleset provenance;
- per-evidence CausLedger Evidence Certificate.

### 7. Durable Proof Pack reconstruction and authenticated export

`vertical_apps/industrial_claims/durable_proof.py`

`vertical_apps/industrial_claims/web.py`

Implemented:

- reconstructs the Proof Pack from tenant-scoped persisted case truth rather than transient in-memory analysis state;
- requires the current revision;
- cross-checks durable finding/evidence/calculation lineage;
- preserves original persisted evidence `received_at`, hashes and metadata;
- exports calculation inputs so the economic result remains independently reproducible;
- exposes authenticated `GET /findings/<finding_id>/proof-pack` to analyst/reviewer/operator roles;
- preserves tenant/actor identity scope checks;
- never claims that current historical digest-only evidence has an immutable raw original when it does not.

### 8. Secure original-evidence capture contract

`vertical_apps/industrial_claims/proof_storage.py`

`vertical_apps/industrial_claims/secure_capture.py`

Implemented:

- provider/object/version/receipt identity contract for immutable originals;
- SHA-256 + SHA-512 + byte-length receipt validation;
- retention mode / legal hold metadata;
- fail-closed unconfigured original store;
- server-controlled first-seen time;
- separately declared effective time;
- delayed-evidence flag when effective time predates first-seen time;
- capture actor/subject/session/device/request provenance;
- authentication-method (`amr`) capture with explicit strong-authentication classification;
- source-authentication receipt contract;
- secure capture refuses a storage receipt whose hashes do not reproduce the captured bytes.

The repository contains the contract and verification logic. A real immutable object-store provider still must be configured before WORM can be claimed live.

### 9. Email forensic provenance

`vertical_apps/industrial_claims/email_forensics.py`

Implemented:

- hashes the original RFC822 `.eml` bytes with SHA-256/SHA-512;
- preserves Message-ID, Date, From/To/Cc/Reply-To, In-Reply-To and References;
- preserves Received, DKIM-Signature and Authentication-Results headers;
- hashes decoded attachments independently with SHA-256/SHA-512 and byte length;
- explicitly treats merely present DKIM headers as `DKIM_PRESENT_UNVERIFIED`;
- only upgrades source authentication when an external/cryptographic authentication receipt exists.

### 10. Proof-strength gate model

`vertical_apps/industrial_claims/proof_readiness.py`

Implemented without numeric confidence theatre. Possible infrastructure levels are:

- `UNVERIFIED`;
- `INTERNAL_INTEGRITY_VERIFIED`;
- `ORIGINAL_IMMUTABILITY_VERIFIED`;
- `INDEPENDENT_TIME_VERIFIED`;
- `QUALIFIED_ORIGIN_VERIFIED`;
- `MULTI_WITNESS_VERIFIED`;
- `MAXIMUM_INFRASTRUCTURE_VERIFIED`.

`MAXIMUM_INFRASTRUCTURE_VERIFIED` requires, among other gates, original-byte preservation, WORM, qualified timestamp, qualified seal/signature, independent provider quorum, public anchor, source authentication for all evidence, dual-hash coverage and evidence escrow. Counterparty acknowledgement is reported separately because it is materially powerful but cannot always be obtained.

### 11. Privacy-preserving transparency batches

`vertical_apps/industrial_claims/transparency.py`

Implemented:

- per-subject salted commitment;
- Merkle aggregation of case-chain commitments;
- private local batch manifest;
- public anchor payload containing only batch ID, leaf count and Merkle root;
- no tenant/customer/finding identity in the public anchor payload.

A real external transparency-log/anchor provider is still required before the root is independently witnessed.

### 12. Factory Cloud wait-state integrity

The CausLedger application remains disabled for production runtime while business-side assisted progress continues. The control plane now explicitly validates `assisted_business_runtime_wait` rather than silently skipping its disabled state. It enforces the `business:real-case` baton and preserves the runtime-provisioning gate.

## Mandatory production target

The maximum-strength production configuration is:

1. verified account identity;
2. MFA/passkey/WebAuthn;
3. tenant isolation;
4. direct-source capture where available;
5. original object retained unchanged;
6. SHA-256 + SHA-512 at ingestion;
7. source-specific authentication (e.g. DKIM/email signature, signed PDF, authenticated API source);
8. server-controlled `first_seen_at`;
9. separately declared `effective_at`;
10. external qualified timestamp where appropriate;
11. immutable/WORM object storage with retention lock;
12. append-only application ledger;
13. hash chaining;
14. Merkle aggregation;
15. periodic independent external root anchoring;
16. HSM/KMS-backed non-exportable signing/sealing keys;
17. second-person review for critical conclusions;
18. contradiction/adverse-evidence preservation;
19. counterparty factual acknowledgement where possible;
20. qualified electronic seal/signature where appropriate;
21. external evidence escrow for high-value cases;
22. signed calculation + ruleset/software provenance;
23. immutable supersession rather than deletion;
24. final Evidence Certificate + Proof Pack;
25. QR/verification identifier in human-facing dossier;
26. privacy-minimal public verification service;
27. offline/open-format verifier so verification does not depend on CausLedger continuing to exist.

## Source capture requirements

For each evidence item, preserve when available:

- original filename/object ID;
- MIME type;
- byte length;
- source URI/account/object reference;
- sender/recipient/message ID for email;
- full email headers and original `.eml` when securely stored;
- DKIM/SPF/DMARC result where technically available;
- original digital-signature/certificate validation result;
- authenticated connector/API object ID;
- received/first-seen timestamp;
- declared effective timestamp;
- capture actor/session/device/request identifier;
- SHA-256;
- SHA-512;
- immutable-storage receipt;
- external timestamp receipt;
- later corroboration/review/acknowledgement states.

## Chronology / anti-backdating

A user may declare that an event happened in the past. That declared time MUST NOT replace the CausLedger first-seen time.

Example:

- `effective_at = 2026-05-03T09:15:00Z` — asserted event time;
- `first_seen_at = 2026-08-31T22:14:08Z` — immutable time the platform first recorded the assertion/evidence.

The UI/export must display both. Delayed evidence must remain visibly delayed.

## Counterparty acknowledgement

Counterparty acknowledgement is a separate factual proof layer. It can acknowledge a narrow fact (e.g. drawing revision received, instruction issued, meeting held) without implying admission of liability or debt. Liability/recoverability remains separately reviewed.

## Contradiction and adverse evidence

CausLedger MUST preserve evidence that weakens recovery as well as evidence that supports it. A Proof Pack should be able to include an `Evidence Against Recovery` section. Contradictory evidence cannot be silently deleted to improve the apparent claim.

## Semantic change proof

For versioned documents CausLedger should preserve:

- before version hash;
- after version hash;
- deterministic diff artifact;
- domain/human interpretation of commercial meaning;
- reviewer identity;
- timestamp/seal over the diff artifact.

Textual/structural diff alone MUST NOT be represented as proof of commercial significance.

## Causal graph

Target chain:

`REQUEST -> CHANGE -> WORK -> RESOURCE -> COST -> CONTRACT_BASIS -> NOTICE -> RECOVERY`

Every edge must have supporting evidence and a state (`SUPPORTED`, `WEAK`, `CONTRADICTED`, `UNRESOLVED`). A missing edge prevents an unqualified causal conclusion.

## Calculation reproducibility

Every economic result should export:

- all inputs;
- evidence IDs for inputs;
- formula ID/version;
- ruleset version/hash;
- rounding policy;
- currency/FX source and date where applicable;
- output;
- reproducibility hash;
- software/build provenance.

A competent third party should be able to reproduce the calculation without using CausLedger.

## Software provenance

Proof packages should bind the result to:

- source revision;
- build hash;
- calculation-engine version;
- ruleset hash;
- runtime version;
- configuration version relevant to the result.

Software provenance proves what code/configuration was identified, not that the program was bug-free or that the commercial conclusion is correct.

## Supersession / revocation

No certified conclusion is edited in place. Corrections create a new revision/certificate and an append-only supersession record containing:

- old certificate;
- new certificate;
- reason;
- actor;
- timestamp.

The historical certificate remains verifiable.

## CausLedger Evidence Certificate

Each material evidence item can receive an independent certificate containing its identity, source, first-seen time, digests, assurance dimensions and explicit truth boundary. It must distinguish:

- integrity;
- existence at/after a timestamp;
- source authentication;
- corroboration;
- factual truth;
- commercial responsibility;
- legal recoverability.

Only the first four can be mechanically strengthened by proof infrastructure. The latter three require substantive evidence/review and may remain unresolved.

## Production gates still requiring real external infrastructure

The following are intentionally NOT claimed as live merely because interfaces/contracts now exist:

- qualified eIDAS timestamp provider;
- qualified electronic seal/signature provider;
- HSM-backed production keys;
- real WORM/Object Lock provider/retention policy;
- independent public/transparency anchor provider;
- independent evidence escrow;
- secure original-document object store configured with actual production retention;
- cryptographic DKIM/signature validation service for source authentication;
- counterparty acknowledgement workflow with verified external identity/signature where required;
- privacy-minimal public verification/QR service;
- certificate revocation/trust-chain validation service.

Until each is configured, exercised end-to-end and evidenced, its state remains unsatisfied. The Proof Pack and proof-strength evaluator must expose that absence instead of pretending that an interface is proof.

## Non-negotiable truth rule

A valid hash proves integrity relative to the hashed bytes. A valid timestamp proves a time attestation according to the provider's verified semantics. A valid signature/seal authenticates the signer/sealer according to the validated certificate/trust chain. None of those facts alone proves that the commercial narrative is true or legally recoverable.

CausLedger must remain fail-closed and may always return `NO CLAIM` / `UNRESOLVED`.
