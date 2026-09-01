# DebitProof — Data Return and Deletion Procedure

## Current storage boundary
The current pilot product is assisted-local. It does not provide shared cloud persistence. Workspace bundles are client-held and HMAC-protected for integrity; that format does **not** provide confidentiality encryption.

## End-of-pilot procedure
1. Freeze the final case/outcome ledger and verify hashes/audit chain.
2. Return the final workspace bundle and agreed reports to the customer through the agreed channel.
3. Produce a source register showing which bounded inputs were processed.
4. Identify local working copies created for the pilot.
5. Delete working copies that are no longer required for the agreed engagement.
6. Record the operator, timestamp, path/category and deletion action in the pilot completion record.
7. Do not claim forensic/cryptographic secure erasure unless the underlying storage platform independently supports and evidences it.
8. Retain only material that the customer and applicable terms explicitly permit to be retained.

## Secrets
Credentials/API keys should never enter the pilot data set. If one is discovered accidentally, treat it as a security incident, isolate the affected copy and instruct the owner to rotate/revoke the credential through the relevant service.

## Customer-held copies
DebitProof cannot delete copies controlled by the customer. Return/deletion confirmation must distinguish operator-controlled copies from customer-controlled source files.

## Public SaaS gate
A future shared deployment must not reuse this procedure as proof of production deletion. Cloud object lifecycle, database deletion, backups, logs, retention, legal holds and recovery copies require separate production tests before shared customer-data deployment.
