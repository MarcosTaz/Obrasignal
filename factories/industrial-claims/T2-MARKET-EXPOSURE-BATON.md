# Industrial Claims — T2 Market Exposure BATON

Status: ACTIVE
Source class: publication/control pointer only; not the canonical application source tree.

## Reconstructed truth

- Publication branch: `factory/industrial-claims-causledger-v0.23.0`
- Publication branch current evidence HEAD: `84691d225a5afdd6ee1d7c1d8c90ea031c831316`
- Referenced local canonical application HEAD: `9ea86553d8978da1197b5aed9f27cb5b1529d39d`
- Distribution artifact: `causledger-industrial-recovery-mvp-v0.23.0.zip`
- Recorded distribution SHA-256: `3225bf0795db547f24339a7123ef70e1bc983d56ec043e14d30d8fe30ed6dd23`
- Recorded exact-source verification: `203/203 PASS`, smoke PASS, release-integrity PASS.
- Current terminal: `T1_PILOT_CAPABLE`.
- Next terminal: `T2_MARKET_EXPOSED`.

These application facts are inherited only from the existing repository provenance pointer. They are not re-tested by this publication branch.

## DONE

- Froze a repository-only T2 market-exposure BATON.
- Added `SYNTHETIC-PILOT-ADMISSIBILITY-v0.1.md` defining fail-closed admission/rejection rules and a synthetic candidate whose amount is explicitly not a proven entitlement or recovery.
- Added `SYNTHETIC-ASSISTED-PILOT-PACKET-v0.1.md` proving generated intake → evidence classification → transaction linkage → amount reconstruction → admissibility → human-reviewable candidate → `EVIDENCE_REQUIRED`, with entitlement/recovery remaining UNKNOWN.

## ACTIVE

Freeze a narrow pilot ICP/qualification screen for documentary supplier-claim opportunities without naming or contacting real prospects.

## NEXT

1. Freeze a narrow pilot ICP/qualification screen for documentary supplier-claim opportunities without naming or contacting real prospects.
2. Define the minimum commercial evidence required to move from `T2_MARKET_EXPOSED` to a later real-pilot terminal: named prospect evidence, exposure date, response, qualified problem, admissible documents and explicit authorization boundary.
3. Prepare a reversible market-exposure operator pack that can be populated with real prospects only after outreach authority is available.
4. Re-verify the referenced canonical application HEAD and distribution hash from the actual canonical source workspace before any real pilot exposure.

## WAIT

- Real external outreach or commercial messages without explicit authorization.
- Any claim that a prospect, customer, contract, payment, recovery or entitlement exists without evidence.
- Merge/deploy/production/customer-data/secrets/provider/source activation.
- Treating this publication branch as the canonical application source tree.

## BLOCKERS

- Exact canonical source workspace is not available through this publication branch, so application tests and artifact SHA cannot be independently re-run here.

## EXACT NEXT EXECUTABLE ACTION

Create a repository-only ICP and qualification screen that prioritizes industrial buyers with document-rich supplier leakage and fails closed when transaction evidence, contractual basis, reconstructable amount or reviewer access is absent.