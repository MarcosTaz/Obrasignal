# ScopeLedger Recovery BATON — 2026-08-29

## STATE

`RECOVERED_SOURCE_EXACT_HEAD_GREEN / PRODUCTION_LINEAGE_UNPROVEN / WAIT_EXTERNAL_LINEAGE`

## SOURCE

- Recovery branch: `recovery/scopeledger-source-20260829`
- Last independently verified recovery HEAD before this BATON: `05a41621806c9bf1ce142263782772b133cee053`
- Recovery workflow run: `33224493149` — SUCCESS
- Job `recovered-source-integrity`: SUCCESS across exact checkout, archive SHA check, dependency install, Python compile, browser JS syntax, and autonomous P0 integrity/concurrency gate.
- Reconstructed minimal-source archive expected SHA-256: `2cde248ee3fc11fdd5c9c3a97d4f67a0b6d5fd1d22d042d0e9b0f38c51c7100f`.

## DONE

- Preserved recovered application source in an isolated GitHub lane instead of mutating an unverified production source.
- Recovery CI is deterministic and reconstructs the source archive before testing it.
- P0 repairs cover contradictory baseline confirmation, IN_SCOPE proposal prevention, mandatory new proposal after REQUEST_CHANGES, approval-expiry persistence, concurrent SOW idempotency, monotonic concurrent Jira cumulative hours, immutable/idempotent invoice evidence, concurrent payment lost-update prevention, payment-date ordering, and later adversarial isolation/security gates.
- Exact recovery HEAD `05a4162…` is independently CI GREEN.

## PRODUCT TRUTH

The recovered source is a credible working candidate, not verified current Railway production source. Local/recovery green does not establish production green, a real pilot, a real customer, WTP, revenue, invoice payment or recovered value.

## ACTIVE

Production/source lineage verification.

## NEXT

1. Fingerprint the live Railway deployment/source through an authorized Railway/project source when such access is available.
2. Compare live fingerprint/files against the recovered candidate.
3. If identical or reconcilable, port/reapply the integrity fixes to the verified production line.
4. Re-run simulation, backup/restore, concurrency and tenant-isolation gates on that verified line.
5. Only then advance pilot exposure/customer-data work.

## WAIT

- No Railway connector/plugin/project source is available in the current tool environment.
- Historical `scopeledger-railway` ref/commit lineage was previously unresolved.
- No production mutation or deployment is authorized from an unverified recovery source.

## BLOCKERS

Production lineage cannot be proved from this GitHub recovery branch alone.

## RESUME_AT

Obtain an authorized live Railway/source fingerprint and compare it with this recovered candidate. If that boundary remains unavailable, do not overbuild the recovery lane; move to the next portfolio Factory.
