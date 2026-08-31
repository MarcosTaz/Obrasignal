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
- manifest SHA-256 and SHA-512;
- independent manifest/package/Merkle self-verification;
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

A third party can verify a JSON Proof Pack without relying on the CausLedger web application for package/Merkle/manifest integrity. External qualified signatures/timestamps require the corresponding trust-chain validation material/provider verification path.

### 6. Evidence certificates and forensic extensions

`vertical_apps/industrial_claims/proof_extensions.py`

Implemented building blocks:

- dual SHA-256/SHA-512 digest at capture time;
- deterministic textual semantic-diff payload;
- causal graph with evidence on every edge;
- adverse/contradictory evidence register;
- calculation provenance;
- software/build/ruleset provenance;
- per-evidence CausLedger Evidence Certificate.

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
26. public verification portal that exposes only non-confidential verification material;
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

The following are intentionally NOT claimed as live merely because interfaces now exist:

- qualified eIDAS timestamp provider;
- qualified electronic seal/signature provider;
- HSM-backed production keys;
- WORM/Object Lock storage;
- independent public/transparency anchor;
- independent evidence escrow;
- secure original-document store;
- counterparty acknowledgement workflow;
- public verification portal/QR endpoint;
- certificate revocation/trust-chain validation service.

Until each is configured, exercised end-to-end and evidenced, its state remains unsatisfied in the Proof Pack.

## Non-negotiable truth rule

A valid hash proves integrity relative to the hashed bytes. A valid timestamp proves a time attestation according to the provider's verified semantics. A valid signature/seal authenticates the signer/sealer according to the validated certificate/trust chain. None of those facts alone proves that the commercial narrative is true or legally recoverable.

CausLedger must remain fail-closed and may always return `NO CLAIM` / `UNRESOLVED`.
