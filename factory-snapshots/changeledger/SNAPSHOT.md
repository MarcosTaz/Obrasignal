# ChangeLedger durability snapshot — 2026-08-28

Status: METADATA_SNAPSHOT_ONLY — product source remains in the canonical conversation artifact and is NOT yet fully materialized as GitHub files on this branch.

- Product: ChangeLedger / Cumulative Change Delay Defense
- Version: 0.22.1
- Business state: CANDIDATE
- Source base main SHA: 66d43f6fd51cf9cea08016dad335aaa04b711a24
- Historical local source HEAD carried by BATON: befaecce8a1cb931d1afe6f748542ddf904d15b3
- Artifact manifest SHA-256: 483e15546c7b1a5b31067cbe2fa74b3a02c89aac2b6eddb7a01ed47ef83d7dbf
- Tests: 75/75 PASS via `npm test`
- Synthetic delivery dry-run: PASS
- Revenue: 0
- Outbound: 0
- WTP: UNKNOWN
- USD 2,500 pilot price: ASSUMPTION
- Success fee: HOLD / DO NOT QUOTE
- Outbound compliance: BLOCKED
- DGC request: Gmail draft `r4293171257938926382`, NOT SENT
- Preferred first route after compliance + authorization: ProSystems corporate mailbox, request routing to Operations / Project Controls

## Patch 0.22.1

Node 22 test-runner determinism only: canonical `npm test` uses `--test-force-exit` because this runtime retained handles after completed assertions. Product logic is unchanged; failed assertions still return non-zero.

## Remaining hard gates

1. exact truthful commercial sender capacity;
2. valid physical postal address for commercial email;
3. current DGC legal-person opt-out list obtained and checked;
4. final disclosure/opt-out footer;
5. owner outbound authorization;
6. buyer response / real paid-pilot evidence.

## Truth invariants

`DELIVERED != VALUE != RECOVERY != EOT`  
`EXTRA WORK TIME != AUTOMATIC EOT`  
`SCHEDULE DIFFERENCE != CAUSALITY`  
`SUPPORTED SCREENING != LEGAL ENTITLEMENT`  
`PRICE ASSUMPTION != WTP`  
`NOT SENT != NO INTEREST`

This file is a durability marker, not a claim that the full product source has been committed to GitHub.
