# EU CLOUD SWITCHING / MIGRATION CAPITAL NETWORK — BATON

## Mission
Build a pilot-ready commercial product that answers whether an expensive infrastructure switching event should happen, what it will really cost, what migration capital is available, and whether promised economics materialized.

## Source truth
- Repository: `MarcosTaz/Obrasignal`
- Branch: `factory/eu-cloud-switching-migration-capital`
- Draft PR: `#711`
- Branch base: main `66d43f6fd51cf9cea08016dad335aaa04b711a24`
- Current verified implementation HEAD before this BATON commit: `5f569bb78a4453e896a5f3db321f79a3aa112622`
- Focused workflow on that exact HEAD: `Cloud Switching Quality` run #58 = SUCCESS.
- Global ObraSignal Quality remains outside this Factory's terminal gate because it includes unrelated repository/mobile checks; do not modify unrelated product areas merely to hide that signal.
- Current implementation lane remains isolated from main; no automatic merge.

## Terminal scoreboard
- CURRENT_TERMINAL: **T1 — PILOT CAPABLE**
- NEXT_TERMINAL: **T2 — EXTERNAL WTP / FIRST-REVENUE SIGNAL**
- CURRENT_WEDGE: customer-paid independent VMware/infrastructure switching economic assurance; immutable promised-vs-actual reconciliation is the strongest differentiated data loop.
- CURRENT_BOTTLENECK: find and prioritize real pre-migration trigger-qualified organizations, then obtain external willingness-to-pay evidence through authorized market exposure.

## Why T1 is now earned
The exact-current-HEAD focused gate is GREEN after the complete assisted journey was implemented and tested:

`estate readiness → baseline → alternative comparison → incentives → frozen forecast → decision package → SQLite persistence → process-style restart → return → actual reconciliation → variance → benchmark eligibility`.

T1 is technical/pilot capability only. It is NOT proof of demand, pricing, conversion, product-market fit, recurring value, or €1M potential.

## Product truth
Implemented product core now includes:
- infrastructure estate readiness with duplicate/stale/UNKNOWN/missing-capacity/future-timestamp failure gates;
- gross switching cost separated from provider/partner subsidy;
- transition-cost categories including data movement/egress, decommissioning, backup/DR transition, security transition and support transition;
- approved incentive separated from received incentive;
- potential/approved/partial/received/expired incentive lifecycle;
- duplicate incentive IDs fail closed;
- status-quo avoidance and current operating savings kept explicit;
- economic payback separated from customer-cash payback;
- non-positive savings never produce a payback;
- over-subsidy can remain visible as negative customer cash cost but can never produce negative payback duration;
- promised-vs-actual outcome variance;
- immutable pre-migration forecast stored before outcome reconciliation;
- retrospective rewriting of route, forecast cost, duration, run-rate, downtime or incentive is rejected;
- benchmark eligibility requires actual values, allowed evidence strength and independent evidence;
- baseline certainty states KNOWN / ESTIMATED / ASSUMED / UNKNOWN;
- material UNKNOWN baseline inputs fail closed instead of becoming zero;
- phased migration waves, decommission lag/dual run and renewal overlap;
- deterministic synthetic companies with positive, small, neutral and value-destroying migrations;
- independent oracle implementation cross-checking product economics;
- decision outcomes SWITCH / DO_NOT_SWITCH_NOW / RENEW_TEMPORARILY / NEEDS_MORE_EVIDENCE;
- provider-neutral option comparison with separate economic winner and customer-cash winner;
- SQLite persistent tenant-isolated delivery state with content hashes and versioning;
- process-style restart/load preserving estate + decision + options + forecast + outcome;
- runnable standalone pilot WSGI with canonical identity adapter.

## Safety invariants
- Potential credit != approved credit != received value.
- Provider subsidy != operating saving.
- No payback when the recurring economic denominator is non-positive.
- No negative payback duration under over-subsidy.
- Migration executor/customer self-attestation cannot silently become independent benchmark truth.
- Unknown material inputs cannot be silently converted to zero.
- Baseline total must reconcile to the decision case before recommendation.
- Estate must be decision-ready before assisted analysis.
- Forecast must be frozen before outcome measurement and cannot be rewritten retrospectively.
- Data movement compatibility aliases cannot be double-counted.
- Synthetic evidence proves calculation reliability, not demand or WTP.

## Test state
- Focused exact-HEAD workflow exists at `.github/workflows/cloud-switching-quality.yml`.
- Earlier failure on HEAD `1926134...`: 90 tests passed / 5 failed because reconcile fixtures had not yet supplied the newly mandatory estate object.
- The fixtures were repaired without weakening the estate gate.
- Exact HEAD `5f569bb78a4453e896a5f3db321f79a3aa112622`: Cloud Switching Quality run #58 = SUCCESS.
- Complete T1 journey test is included and executed by the focused `tests/test_cloud_switching_*.py` gate.
- Global ObraSignal Quality may remain RED for unrelated repository/mobile reasons and is not silently reclassified as this Factory's product failure.

## Commercial hypothesis state
Persisted but UNVALIDATED:
- working offer: Verified Migration Economics Review;
- Baseline Certification hypothesis: EUR 1,500;
- optional checkpoint hypothesis: EUR 1,000;
- Outcome Verification hypothesis: EUR 3,500;
- lifecycle hypothesis: EUR 5,000–6,000;
- primary cohort: European mid-market / enterprise VMware/infrastructure switching events;
- entry roles: FinOps / ITFM → CTO/CIO/infrastructure → cloud/platform; Finance validates economics;
- first meaningful WTP signal target: paid founding pilots, not free use.

## ACTIVE
Build the first real trigger-qualified prospect universe without sending outreach:
1. discover public VMware/infrastructure switching triggers;
2. preserve source/date/decision deadline/estate signal/alternatives/business-case evidence;
3. score prospects with UNKNOWN preserved;
4. rank Tier A/B;
5. identify likely decision-owner roles;
6. prepare evidence-backed outreach context, but keep send state NOT_AUTHORIZED unless explicit authorization/channel exists.

## NEXT
1. Build first 20–30 high-confidence prospect records from public triggers.
2. Red-team whether those triggers occur early enough to freeze the business case.
3. Refine pricing and assisted-hours model from the actual evidence burden implied by those prospects.
4. Create pilot acceptance/report structure for real customer use.
5. Build anonymized benchmark contribution/consent contract concepts.
6. Define first 5 paid-pilot conversion gates and kill metrics.
7. Only after real WTP evidence, reassess recurring benchmark product and €1M/36-month path.

## WAIT
Only genuine external gates:
- real customer estate/contract/billing/telemetry data;
- real provider incentive approval;
- real migration quote;
- customer authorization;
- external outreach/send channel authorization;
- contracts/payments/deployment to a real external customer.

Commercial proof remains UNKNOWN until external evidence exists.

## RESUME_AT
Resolve exact branch HEAD, preserve T1, then continue ACTIVE prospect-universe construction immediately. Do not restart generic cloud research and do not broaden into generic FinOps/cloud management.
