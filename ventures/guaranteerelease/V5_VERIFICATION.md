# GuaranteeRelease — v5 Verification Record

Date: 2026-08-29

## Canonical-candidate test state

- `engine_v3.test.mjs`: **PASS 23/23**
- `server_v5.test.mjs`: **PASS 38/38**
- `synthetic_replay_v5.test.mjs`: **PASS 41/41**
- v5 browser DOM/runtime E2E: **PASS 31/31 (transport-bridged)**
- Node syntax: **PASS**
- HTML parse: **PASS**
- inline JavaScript syntax: **PASS**

An expanded local API hardening run also passed 41/41 while developing v5; the committed canonical API suite is the 38/38 file above, so the scoreboard uses 38/38.

## Material v5 safety improvements

1. Instrument baseline is not trusted merely because an operator entered it.
2. `INSTRUMENT_TERMS` requires independent reviewer approval before a non-`UNKNOWN` assessment.
3. Instrument type, currency, original/current amount and expiry date must match the approved baseline.
4. Changing a baseline field invalidates prior baseline truth and returns the case to `UNKNOWN` until fresh evidence is approved.
5. Operator and reviewer are separate roles and principals; reviewer cannot create/update/submit and operator cannot review.
6. Ambiguous principal configuration (duplicate identity or duplicate token hash) fails closed.
7. Plaintext legacy API-key configuration no longer authenticates.
8. All writes are attributed to a `principalId` in audit history.
9. Expiry can produce `RELEASE_MAY_BE_DUE` only after the expiry-bearing baseline is independently reviewed, and expiry alone still produces zero potential release.
10. Wrong-project/contract evidence cannot be approved and forces `UNKNOWN` until rejected.

## Seven-case oracle replay

The independent synthetic oracle is replayed through the v5 HTTP workflow with a reviewed baseline for all seven instruments. Results preserve progressive APG reduction, milestone reduction, valid-defect correct zero, release candidate without fabricated cancellation, cancellation separate from collateral release, wrong-project fail-closed `UNKNOWN`, and progress-without-right correct zero.

## Truth not proven

- Native browser HTTP transport on this host: blocked by administrator URL policy.
- Production IAM / SSO / MFA: not implemented.
- Production document ingestion and immutable source-content hashing: not implemented.
- Real customer: 0.
- Real security analyzed: 0.
- Real release/reduction: 0.
- Real collateral/capacity restored: 0.
- Real revenue: 0.
- WTP: unproven.
- Typical actionable percentage of a real portfolio: unknown.
