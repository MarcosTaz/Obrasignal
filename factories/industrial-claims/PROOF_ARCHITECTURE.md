# VINDORUM — EVIDENCE & PROOF ARCHITECTURE

Status: ACTIVE PRODUCT CONTRACT

## Objective
VINDORUM must produce an independently reviewable proof package showing what evidence was received, its provenance and first-seen time, whether it changed, what revision superseded what, which facts are supported or contradicted, how the economics were calculated and which external proof gates remain unproven.

Cryptographic integrity is never presented as proof that a commercial narrative is true, that a customer is responsible or that money is legally recoverable.

## Core objects
### Proof package
`vertical_apps/industrial_claims/proof_package.py`
- core case package;
- proof manifest;
- proof-strength gates;
- internal verification result;
- explicit external-gate status.

### Manifest and verification
`vertical_apps/industrial_claims/proof.py`
- canonical JSON;
- SHA-256/SHA-512 package and evidence digests;
- Merkle root;
- evidence-assurance state machine;
- stable external-attestation target;
- fail-closed verification;
- truth-boundary declarations.

Evidence assurance is progressive:
`UNVERIFIED → SOURCE_AUTHENTICATED → INTEGRITY_SEALED → TIME_SEALED → CORROBORATED → HUMAN_REVIEWED → COUNTERPARTY_ACKNOWLEDGED → QUALIFIED_SEALED`

These are proof dimensions, not recoverability scores.

### Append-only proof ledger
`vertical_apps/industrial_claims/proof_store.py`
- server-controlled first-seen time separate from declared effective time;
- append-only case events and hash chaining;
- immutable attestation/certificate/supersession records;
- UPDATE/DELETE rejection;
- tenant scoping;
- certificate issuance blocked on chain-verification failure.

Application append-only storage is not called WORM. WORM remains an external gate.

### External providers
`vertical_apps/industrial_claims/proof_providers.py`
Interfaces exist for timestamping, seal/signature, WORM/Object Lock, public anchoring and evidence escrow. Default/unconfigured providers remain unavailable and fail closed.

### Offline verification
`vertical_apps/industrial_claims/proof_verifier.py`
A third party can verify package/Merkle/manifest integrity without depending on the VINDORUM web application. External qualified signatures/timestamps still require their trust-chain/provider verification material.

### Evidence certificates and extensions
`vertical_apps/industrial_claims/proof_extensions.py`
- dual hashes;
- deterministic semantic-diff payload;
- causal graph with evidence on every edge;
- adverse-evidence register;
- calculation provenance;
- software/build/ruleset provenance;
- per-evidence certificate.

### Durable reconstruction
`vertical_apps/industrial_claims/durable_proof.py`
Proof packages must reconstruct from tenant-scoped persisted current case truth, not transient analysis state, and preserve original received-at/hash/provenance values.

### Secure original capture
`vertical_apps/industrial_claims/proof_storage.py`
`vertical_apps/industrial_claims/secure_capture.py`
- immutable-original receipt contract;
- SHA-256/SHA-512 and byte-length validation;
- retention/legal-hold metadata;
- server first-seen time;
- effective-time separation and delayed-evidence flag;
- actor/session/device/request provenance;
- source-authentication receipt;
- fail closed on digest mismatch or unconfigured provider.

### Email provenance
`vertical_apps/industrial_claims/email_forensics.py`
Original RFC822 bytes and decoded attachments are hashed. Message/thread/authentication headers are preserved. A present DKIM header is not treated as verified authentication without actual verification evidence.

### Proof readiness
`vertical_apps/industrial_claims/proof_readiness.py`
Infrastructure levels:
`UNVERIFIED → INTERNAL_INTEGRITY_VERIFIED → ORIGINAL_IMMUTABILITY_VERIFIED → INDEPENDENT_TIME_VERIFIED → QUALIFIED_ORIGIN_VERIFIED → MULTI_WITNESS_VERIFIED → MAXIMUM_INFRASTRUCTURE_VERIFIED`

No level may be claimed without its actual external evidence.

## Required production properties
Production evidence handling requires, as applicable:
1. verified account identity and strong authentication;
2. tenant/case isolation;
3. direct-source capture where available;
4. unchanged original preservation;
5. dual hashes at ingestion;
6. source-specific authentication;
7. server-controlled first-seen time;
8. explicit effective time;
9. verified timestamp provider;
10. verified WORM/Object Lock with retention;
11. append-only application ledger and hash chain;
12. periodic independent anchoring where justified;
13. protected signing/sealing keys where used;
14. contradiction/adverse-evidence preservation;
15. immutable supersession rather than deletion;
16. reproducible calculation/ruleset/software provenance;
17. evidence certificate + proof package;
18. offline/open-format verification.

Until production auth, secure transfer, WORM, timestamping, retention/deletion and required security/privacy controls are configured and tested, `real_evidence_intake_enabled` must remain false.

## Chronology / anti-backdating
A declared historical event time never replaces VINDORUM's first-seen time. Both must be visible, and delayed evidence stays visibly delayed.

## Contradictory evidence
Evidence that weakens a candidate is preserved with the same discipline as supporting evidence. Contradictory evidence cannot be silently removed to improve apparent recovery.

## Causal graph
Target chain:
`REQUEST → CHANGE → WORK → RESOURCE → COST → COMMERCIAL_BASIS → NOTICE → RECOVERY_STATE`

Every edge must have evidence and a state such as `SUPPORTED`, `WEAK`, `CONTRADICTED` or `UNRESOLVED`. Missing edges prevent unqualified causal conclusions.

## Economic reproducibility
Every economic result exposes inputs, evidence IDs, formula/ruleset version, rounding, currency/FX evidence when applicable, output and reproducibility hash.

The recovery ledger remains:
`documented cost → mitigation → net documented exposure → evidence-supported → claimed → approved → settled`

Required invariant:
`net documented exposure >= evidence-supported >= claimed >= approved >= settled`

## Supersession
Certified conclusions are not edited in place. Corrections create a new revision and immutable supersession record; historical revisions remain verifiable.

## External infrastructure still not assumed live
Interfaces/contracts alone do not prove live operation of qualified timestamps, seals/signatures, HSM-backed keys, WORM storage, public anchoring, evidence escrow, cryptographic source authentication, counterparty identity/signature, public verification or trust-chain validation.

Each stays unsatisfied until configured, exercised end-to-end and evidenced.

## Non-negotiable truth rule
A hash proves integrity relative to bytes. A timestamp proves only the provider's verified time attestation. A signature/seal authenticates only according to the validated trust chain. None alone proves factual truth, customer responsibility or legal recoverability.

VINDORUM remains fail closed and may return `NO CLAIM`, `NEEDS EVIDENCE` or `UNRESOLVED`.
