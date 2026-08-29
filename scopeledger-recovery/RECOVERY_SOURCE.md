# ScopeLedger source recovery — 2026-08-29

Status: **RECOVERED SOURCE CANDIDATE — NOT YET PROVEN TO BE THE CURRENT RAILWAY SOURCE**.

Why this exists:
- the previously cited `scopeledger-railway` GitHub ref and historical commit IDs were not resolvable during exact-source recovery;
- a persistent Library snapshot contained the ScopeLedger application source (`main.py`, `core.py`, `app.js`, `app.css`) and GTM asset;
- this branch preserves that source in an isolated recovery lane rather than mutating production blindly.

Current recovery evidence:
- Python source compiles;
- 9 integrity/adversarial tests pass locally;
- recovered P0 repairs cover contradictory baseline confirmation, IN_SCOPE proposal prevention, mandatory new proposal after REQUEST_CHANGES, approval-expiry persistence, concurrent SOW idempotency, monotonic concurrent Jira cumulative hours, immutable/idempotent invoice evidence, concurrent payment lost-update prevention, and payment-date ordering.

Truth boundary:
- RECOVERED SOURCE != CURRENT PRODUCTION SOURCE until byte/source lineage to Railway is proven.
- LOCAL GREEN != PRODUCTION GREEN.
- SYNTHETIC TEST PASS != COMMERCIAL VALIDATION.

Archive:
- concatenate `source.min.zip.b64.part-00` .. `part-02`;
- base64-decode to `source.min.zip`;
- expected SHA-256: `2cde248ee3fc11fdd5c9c3a97d4f67a0b6d5fd1d22d042d0e9b0f38c51c7100f`.

Next:
1. run the recovery CI on this branch;
2. fingerprint the live Railway app/source if accessible;
3. reconcile differences before any production deployment;
4. port the integrity fixes to the verified production source;
5. repeat simulation + backup/restore + concurrency gates.
