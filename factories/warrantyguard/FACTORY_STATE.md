# WARRANTYGUARD — Factory State / BATON

## MISSION
Build and validate an independent supplier-side automotive debit-truth company + assisted product that prevents unsupported OEM/customer warranty/quality debits from becoming accepted accounting truth, without fabricating liability, recovery, rights, customers or revenue.

## CLASSIFICATION
`NARROW → PROCEED`

## VERSION / SOURCE TRUTH
VERSION = `0.8.4`
RUNTIME = `Node.js >=20 / zero external npm dependencies`
TEST_STATE = `52/52 PASS`
REDTEAM = `10,000 debit cases + 1,000 recovery cases PASS`
ORACLE = `18/18 PASS`
SYNTHETIC_PORTFOLIO = `6 companies / 18 cases / 4 UNKNOWN / 10 draft packs`
ARTIFACT_SHA256 = `333c35bc1cf1bbb2af1fc272ad477d3784ad4d2f762b9bed7b461077fc77368f`
SOURCE_DURABILITY = `manifest + required-file guard + commercial-state guard + clean extraction/retest + Library persistence`.

## DURABILITY INCIDENT — REPAIRED
On 2026-08-29 the working BATON claimed a later 52-test source while the recoverable archive still contained v0.1 / 22 tests / Next.js dependencies. That archive was rejected as source truth. v0.8.4 was reconstructed as zero-dependency executable source. The replacement archive passed a clean extraction and full re-verification and is persisted at `/WarrantyGuard/warrantyguard-prototype-v0.8.4.tar.gz` in the user's ChatGPT Library.

## CURRENT WEDGE
**Pre-acceptance financial control for recurring inbound OEM/customer warranty and quality debits.**

INCOMING DEBIT → strict tenant-scoped import → mapping completeness → applicable approved contract/CSR/warranty version + hash lineage → evidence presence/integrity + review lineage → warranty/cost eligibility → root-cause/responsibility → duplicate/prior-credit/payment → SUPPORTED / PARTIALLY_SUPPORTED / DISPUTABLE / UNKNOWN → draft-only action pack → approved/received credit + cash reconciliation → verified outcome.

UNKNOWN exposes no supported/disputable money. Missing part/program/asset is UNKNOWN, never inferred WRONG_*. Potential duplicate never auto-rejects. Prior payment is not prior credit. Draft dispute is not recovery. Credit/cash are not double-counted by default.

## PRODUCT BOUNDARY
`ASSISTED_LOCAL / NO SHARED PERSISTENCE / HUMAN_REVIEW_REQUIRED`

Implemented: strict quoted CSV parsing; 500-row/2MB pilot bounds; ISO date and currency validation; tenant checks; contract effective/version selection; contract source/rules hashes; approval fields; evidence hashes/claims/reviewer lineage; missing mapping fail-closed; responsibility/warranty/cost logic; exact/fuzzy duplicate separation; prior credit/payment separation; currency-separated summaries; UNKNOWN money suppression; draft-only dispute packs; evidence-gated recovery measurement; local API; token-protected operator endpoint; operator CLI; source register/hashes; synthetic oracle; deterministic red-team; tenant-namespaced pseudonymization helper.

Public/multi-user customer-data deployment remains blocked until AuthN/AuthZ, secure persistence/secrets, audit logs, backup/restore, deletion workflows, monitoring, rollback and security review are verified.

## TERMINALS
T1 = `PASSED — ASSISTED_LOCAL`
CURRENT_TERMINAL = `T2 — MARKET EXPOSED`
NEXT_TERMINAL = `T3 — COMMERCIAL PROOF`

## REAL EXPOSURE EVIDENCE
1. AFIA → `info@afia.pt` — Gmail `1a04dd405f82f212` — SENT
2. Simoldes Plastics → `alexandre.batista@simoldes.com` — Gmail `1a04dd750c85a135` — SENT
3. FEHST Componentes → `fehst.comp@fehstgroup.com` — Gmail `1a04df7aca576132` — SENT
4. PLASTIFA → `plastifa@plastifa.pt` — Gmail `1a04df81b959496f` — SENT

LATEST_RESPONSE_CHECK = `2026-08-29T19:54+01:00`
Each thread contained exactly one message, the sent message. OBSERVABLE_REPLY_OR_BOUNCE = `NONE`. Sent != delivered/read/replied.

## OFFER
Working offer: `DebitProof — Debit Acceptance Control`. Pricing hypotheses only: bounded diagnostic €2,500–€5,000; assisted pilot €7,500–€15,000. Recurring/outcome components require real repeat-value and measurement/legal/commercial proof.

## COMMERCIAL TRUTH
MARKET_STATE = `T2 REACHED`
WTP_STATE = `UNPROVEN DIRECTLY`
DATA_AVAILABILITY_REAL = `UNKNOWN`
REAL_CUSTOMERS = `0`
PAID_PILOTS = `0`
REAL_DISPUTABLE_VALUE = `€0`
VERIFIED_RECOVERY_REAL = `€0`
REVENUE_RECEIVED = `€0`
Synthetic outcome evidence is never included in real metrics.

## T3 GATE
Reply, email open, meeting, demo, generic interest or non-sensitive sample willingness do not count. T3 requires a paid diagnostic/pilot, signed commercial commitment with credible budget/procurement path, or equivalent independently observable costly behavior.

## MARKET CONTROL
CURRENT_COHORT = `4 / frozen during initial response window`
NEXT_EXPOSURE_STATUS = `COHORT_FROZEN_WAITING_RESPONSE`
EARLIEST_CONTROLLED_FOLLOWUP = `2026-09-03T09:00:00+01:00`
Follow-up only when no reply, bounce, rejection or reroute exists on that lane. Standby after the cohort gate: JAC Products Portugal → TMG Automotive, each with collision check first.

## ACTIVE
`T3_RESPONSE_QUALIFICATION + SAFE PRODUCT/OPERATION HARDENING`

## NEXT
1. monitor four real Gmail lanes;
2. triage any response fail-closed;
3. qualify materiality/owner/deadline/incumbent/data/WTP without leading;
4. seek a bounded paid diagnostic only when commercial/security gates survive;
5. on 2026-09-03, send one controlled follow-up only to eligible lanes;
6. if no signal after controlled follow-up, open standby targets one by one after collision check;
7. narrow/reject if incumbent controls already solve the full pre-acceptance finance gate adequately;
8. never deploy customer-data SaaS before production security gates.

## WAIT / BLOCKERS
T3 depends on external market behavior. This is a local blocker only. Public customer-data deployment is intentionally blocked by security gates; assisted-local delivery remains executable.

## RESUME_AT
`MONITOR_4_THREADS → TRIAGE_REAL_RESPONSE → QUALIFY → PAID_DIAGNOSTIC_OR_KILL → CONTROLLED_FOLLOWUP_2026-09-03_IF_ELIGIBLE → NEXT_TARGET → T3_OR_NARROW`
