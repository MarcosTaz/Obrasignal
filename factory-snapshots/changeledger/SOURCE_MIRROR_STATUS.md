# ChangeLedger source mirror status — 2026-08-28

Status: METADATA-ONLY SNAPSHOT.

The isolated branch `factory/changeledger-cumulative-delay-snapshot-20260828` intentionally does **not** claim to contain the full ChangeLedger source tree.

Current canonical restorable product artifact remains the validated ZIP produced in the execution environment. The branch contains continuity metadata, checksums and BATON state only.

Why the full ZIP/source was not mirrored in this execution:
- the connected GitHub actions can create UTF-8 repository content and Git objects;
- the canonical artifact is a local binary ZIP;
- there is no direct local-file upload parameter on the available GitHub write actions;
- retransmitting the binary through model text would be a high-risk/low-value durability workaround and was not represented as completed.

Truth invariants:
- `main` was not modified by ChangeLedger.
- no ChangeLedger PR was opened.
- do not treat this branch as a source mirror until explicit source files or a restorable archive are actually materialized here.
- the BATON must continue to identify the validated ZIP as the canonical source artifact until that happens.

Outbound state remains separate from source durability: the product is technically test-green, but commercial outbound remains blocked by a valid physical postal address, authoritative current DGC-list consultation, and owner authorization.
