# Industrial Claims — T2 Market Exposure BATON

Status: WAIT_EXTERNAL
Source class: publication/control pointer only; not the canonical application source tree.

## Reconstructed truth

- Publication branch: `factory/industrial-claims-causledger-v0.23.0`
- Publication branch current evidence HEAD: `1a10644e8a2e60a09374a17d924532f0787ff265`
- Referenced local canonical application HEAD: `9ea86553d8978da1197b5aed9f27cb5b1529d39d`
- Distribution artifact: `causledger-industrial-recovery-mvp-v0.23.0.zip`
- Recorded distribution SHA-256: `3225bf0795db547f24339a7123ef70e1bc983d56ec043e14d30d8fe30ed6dd23`
- Recorded exact-source verification: `203/203 PASS`, smoke PASS, release-integrity PASS.
- Current terminal: `T1_PILOT_CAPABLE / T2_PREPARED_NOT_EXPOSED`.
- Next external terminal: `T2_MARKET_EXPOSED`.

These application facts are inherited only from the existing repository provenance pointer. They are not re-tested by this publication branch.

## DONE

- Froze a repository-only T2 market-exposure BATON.
- Added `SYNTHETIC-PILOT-ADMISSIBILITY-v0.1.md` defining fail-closed admission/rejection rules and a synthetic candidate whose amount is explicitly not a proven entitlement or recovery.
- Added `SYNTHETIC-ASSISTED-PILOT-PACKET-v0.1.md` proving generated intake → evidence classification → transaction linkage → amount reconstruction → admissibility → human-reviewable candidate → `EVIDENCE_REQUIRED`, with entitlement/recovery remaining UNKNOWN.
- Added `PILOT-ICP-QUALIFICATION-v0.1.md` with a document-first 14-point qualification screen and explicit NOT_QUALIFIED/EVIDENCE_REQUIRED/ASSISTED_PILOT_CANDIDATE terminals.
- Added `T2-TO-REAL-PILOT-EVIDENCE-GATE-v0.1.md` separating exposure, pilot candidacy, acceptance, started work, candidate value, defensible claim, recovered value and platform revenue.
- Added `MARKET-EXPOSURE-OPERATOR-PACK-v0.1.md` with a narrow assisted offer, qualification prompts, message skeleton, prospect record and evidence-preserving execution checklist.

## ACTIVE

No further repository-only T2 preparation task is higher value on this publication lane.

## NEXT

1. Re-verify the referenced canonical application HEAD and distribution hash from the actual canonical source workspace before real pilot exposure.
2. Select and verify a real prospect only in an authorized external-research/outreach lane.
3. Expose the frozen offer and preserve transmission evidence.
4. Qualify any response against the ICP screen without upgrading state from narrative alone.

## WAIT

- Access to the exact canonical application source workspace for independent source/artifact verification.
- A real external market-exposure lane/authority and verified prospect evidence.
- Any claim that a prospect, customer, contract, payment, recovery or entitlement exists without evidence.
- Merge/deploy/production/customer-data/secrets/provider/source activation.

## BLOCKERS

- Exact canonical source workspace is not available through this publication branch, so application tests and artifact SHA cannot be independently re-run here.
- No real prospect/transmission evidence exists on this lane; therefore `T2_MARKET_EXPOSED` cannot be claimed.

## RESUME_AT

Re-verify canonical source/artifact when accessible; otherwise ingest a verified external exposure event and apply the T2 evidence gate.

## EXACT NEXT EXECUTABLE ACTION

None on this repository-only lane without crossing an external/canonical boundary. Move to the next portfolio Factory.