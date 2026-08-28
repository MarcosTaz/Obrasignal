# EU CLOUD SWITCHING / MIGRATION CAPITAL NETWORK — BATON

## Mission
Build a pilot-ready commercial product that answers whether an expensive infrastructure switching event should happen, what it will really cost, what migration capital is available, and whether promised economics materialized.

## Source truth
- Repository: `MarcosTaz/Obrasignal`
- Branch: `factory/eu-cloud-switching-migration-capital`
- Draft PR: `#711`
- Branch base: main `66d43f6fd51cf9cea08016dad335aaa04b711a24`
- Current implementation lane is isolated from main; no automatic merge.

## Terminal scoreboard
- CURRENT_TERMINAL: T0 — WEDGE SURVIVED
- NEXT_TERMINAL: T1 — PILOT CAPABLE
- CURRENT_WEDGE: customer-paid independent VMware/infrastructure switching economic assurance; promised-vs-actual reconciliation is the strongest differentiated data loop.
- CURRENT_BOTTLENECK: prove exact-current-HEAD calculation integrity, then expose one complete assisted decision-package journey.

## Product truth
Implemented economic core now includes:
- gross switching cost separated from provider/partner subsidy;
- approved incentive separated from received incentive;
- potential/approved/partial/received/expired incentive lifecycle;
- duplicate incentive IDs fail closed;
- status-quo avoidance and current operating savings kept explicit;
- economic payback separated from customer-cash payback;
- non-positive savings never produce a payback;
- over-subsidy can remain visible as negative customer cash cost but can never produce negative payback duration;
- promised-vs-actual outcome variance;
- benchmark eligibility requires actual values, allowed evidence strength and independent evidence;
- baseline certainty states KNOWN / ESTIMATED / ASSUMED / UNKNOWN;
- material UNKNOWN baseline inputs fail closed instead of becoming zero;
- phased migration waves, decommission lag/dual run and renewal overlap;
- deterministic synthetic companies with positive, small, neutral and value-destroying migrations;
- independent oracle implementation cross-checking product economics;
- decision outcomes SWITCH / DO_NOT_SWITCH_NOW / RENEW_TEMPORARILY / NEEDS_MORE_EVIDENCE.

## Safety invariants
- Potential credit != approved credit != received value.
- Provider subsidy != operating saving.
- No payback when the recurring economic denominator is non-positive.
- No negative payback duration under over-subsidy.
- Migration executor/customer self-attestation cannot silently become independent benchmark truth.
- Unknown material inputs cannot be silently converted to zero.
- Baseline total must reconcile to the decision case before recommendation.
- Synthetic evidence proves calculation reliability, not demand or WTP.

## Test state
- Draft PR #711 created solely to exercise exact-HEAD CI; it is not merged.
- First observed PR HEAD `8dac2e72860b981f6aafbde05449da5a674e646e`: Python quality job GREEN, including repository tests.
- Global quality job remains RED because unrelated mobile `expo-doctor` expects react-native 0.86.3 while repository mobile has 0.86.2. This Factory has not modified mobile to hide that unrelated failure.
- Later Python runs are executing as the branch advances.
- Added focused `.github/workflows/cloud-switching-quality.yml` so cloud-switching exact-HEAD validity is not masked by unrelated mobile drift.
- Latest branch HEAD at time of this baton update is the focused-workflow commit `c9fc2c3fe608c33cc65e1c6a0e55dfb55593c073` plus this baton commit when written; re-resolve HEAD before next mutation.

## P0 / P1
- P0: none currently observed in cloud-switching domain.
- P1 repaired this turn: non-independent customer evidence entering verified benchmark.
- P1 repaired this turn: over-subsidy producing negative payback duration.
- P1 guards added: unknown material baseline, false/duplicate/expired incentive capture, value-destroying migration, unreconciled baseline.
- P1 status remains NOT_FULLY_VERIFIED until exact-current-HEAD focused CI is observed GREEN.

## ACTIVE
Observe focused exact-current-HEAD cloud-switching CI. If red, repair immediately. If green, build the assisted T1 decision package joining baseline + option economics + incentives + phased cost + decision + promised-vs-actual evidence into one deterministic output.

## NEXT
1. Add decision-package service with executive summary and audit trail.
2. Add option comparison across retain/renew, AWS/Azure/GCP/alternative virtualization without provider bias.
3. Add currency/evidence-lineage/comparability guards.
4. Add adversarial malformed/duplicate/stale/currency cases.
5. Add minimal read-only API/UI after domain service is green.
6. Add tenant isolation/persistence/backup-restore tests before T1 terminal.
7. Define ICP/offer/price hypothesis for T2 only after T1 is technically credible.

## WAIT
Only genuine external gates: real customer estate/contract data, real provider incentive approval, real migration quote, customer authorization, external outreach/payment/contracts/deployment. Commercial proof remains unproven.

## RESUME_AT
Resolve exact branch HEAD and focused workflow result first. Continue T1 implementation immediately; do not restart research or broaden into generic cloud management.
