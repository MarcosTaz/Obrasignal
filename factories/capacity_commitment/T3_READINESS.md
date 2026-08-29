# Capacity Commitment — T3 Pilot Readiness Matrix

Status: **OPERATIONALLY READY FOR A BOUNDED ASSISTED CASE / COMMERCIAL PROOF NOT YET ACHIEVED**

This file separates what is actually ready from what still depends on a real buyer or external account/compliance event.

Latest validated code/test head before this documentation reconciliation: `996473147b623a677b6879fc028a5534db08017b`, engine `capacity-recoverability-t1.12`, exact-head Python **949 passed / 2 skipped / 2 warnings** in `ObraSignal Quality` run `33270658282`. The unrelated mobile/Expo lane remains red and is not represented as green.

## Terminal truth

- T0 — distinct thesis survived: **ACHIEVED**
- T1 — pilot capable: **ACHIEVED / CURRENTLY HARDENED**
- T2 — market exposed: **ACHIEVED**
- T3 — commercial proof: **NOT YET ACHIEVED**
- T4 — verified economic value + our revenue: **NOT YET ACHIEVED**
- T5 — repeatable business: **NOT YET ACHIEVED**

No stronger terminal is inferred from technical readiness.

## Buyer-conversion readiness

| Capability | State | Evidence / boundary |
| --- | --- | --- |
| Narrow ICP/wedge | READY | automotive supplier volume/dedicated-investment recoverability assurance |
| Live market exposure | PROVEN | five unique UK companies transmitted through corporate routes |
| First-cohort follow-up | READY / SCHEDULED | five clean threaded drafts; reply/bounce/opt-out/suppression pre-check required |
| Second UK cohort | READY / SCHEDULED | EVTEC + AC Plastics drafts; not CONTACTED until actual send |
| Reply classification | READY | `T3_CONVERSION.md` |
| Buyer response copy | READY | `T3_RESPONSE_KIT.md` |
| One-page commercial explanation | READY | `T3_ONE_PAGER.md` |
| Synthetic product demonstration | READY | `T3_SYNTHETIC_DEMO.md`, explicitly not customer proof |
| Buyer-qualified real case | NOT PROVEN | requires real buyer behavior |
| WTP | NOT PROVEN | price remains hypothesis |

## Real-case intake readiness

| Capability | State | Evidence / boundary |
| --- | --- | --- |
| One-program eligibility gate | READY | `T3_CONVERSION.md` |
| Bounded minimum dataset | READY | `T3_INTAKE.md` |
| Identity freeze / source-version discipline | READY | intake + delivery runbook |
| Confidential-data public-repo exclusion | READY | `T3_CONFIDENTIAL_DATA.md` |
| Authorized buyer transfer route | EXTERNAL / UNKNOWN | buyer-specific; do not invent |
| NDA/DPA/customer contractual requirements | EXTERNAL / UNKNOWN | establish only if required by the real buyer/process |
| Real proprietary data | NOT PROVEN | none received |

## Product execution readiness

| Capability | State | Evidence / boundary |
| --- | --- | --- |
| Fail-closed recoverability engine | READY | t1.12 + exact-head regressions |
| Deterministic exact arithmetic | READY | isolated Decimal context; float rejection; range failures become invalid input |
| Forecast kept separate from firm entitlement | READY | engine/tests |
| Zero-effective commitment handling | READY | FIRM/FLEX zero effective units cannot become positive recoverability |
| Customer/program/period/unit/currency integrity | READY | engine/tests; ASCII currency identity enforced |
| Contract/amendment/notice gates | READY | engine/tests |
| Time-sensitive deadline aging | READY | verified deadline re-evaluated against explicit/UTC assessment date |
| Mitigation/prior-recovery deductions and review | READY | engine/tests |
| Duplicate-claim review | READY | positive position requires explicit completed duplicate search; known duplicate blocked |
| Correct-zero truth | READY | zero cannot be upgraded from unverified zero-producing inputs |
| Exact API evidence boundary | READY | material booleans and financial values explicit; decimal strings/integers only |
| Tenant-scoped persistence | READY | repository/web tests |
| Exact snapshot structure | READY | checksum plus exact schema-v2 top-level and nested `RecoveryCase` field sets |
| Retry/conflict/restart durability | READY | T1 tests |
| Canonical backup/restore | READY | canonical schema only; source rows validated before mutation; samefile aliases rejected |
| Existing-case browser | READY | authenticated `/cases`, tenant scoped |
| Buyer-ready findings report | READY | authenticated `/api/capacity/cases/<case_id>/report` |
| Package direct-call truth boundary | READY | current-result, evidence, deadline, assessment-date and expiry consistency enforced |
| Report restart/current-state integrity | READY | package recomputation + stale/mutated-package rejection |
| Report source/Markdown injection hardening | READY | adversarial test |
| Web/repository case-ID addressability | READY | one safe identity policy across create/load/list/restore |
| Automatic raw-contract extraction | NOT REQUIRED FOR CURRENT ASSISTED PILOT | manual review remains intentional boundary |
| Automated external claim submission | NOT AUTHORIZED / NOT REQUIRED | human action only |
| Production-hosted public/self-service app | NOT PROVEN / NOT REQUIRED FOR FIRST ASSISTED PILOT | isolated runtime is not claimed deployed |

## Commercial scope readiness

| Capability | State | Evidence / boundary |
| --- | --- | --- |
| Bounded pilot scope | READY | `T3_PILOT_SCOPE.md` |
| Fixed price hypothesis | READY TO TEST, NOT PROVEN | £3,000 UK / €3,500 euro markets |
| Hybrid hypothesis | READY TO TEST CONDITIONALLY | setup + 7.5% incremental attributable cash received |
| Correct-zero fee logic | READY | fee pays for forensic determination, not manufactured claim |
| Unit-economics guardrails | READY | `T3_UNIT_ECONOMICS.md` |
| Real buyer price acceptance | NOT PROVEN | no priced-pilot acceptance |
| Signed agreement | NOT PROVEN | none exists |
| Invoice | NOT ISSUED | must not be confused with payment |
| Payment | NOT RECEIVED | no revenue claim |

## Payment rail

Current connected payment context does not expose a Capacity Commitment account. The previously visible K3 Fatality account belongs to another Factory and is prohibited for Capacity funds.

Capacity Commitment payment state:

- correct Capacity payment account: **EXTERNAL / NOT CONNECTED OR VERIFIED**
- Capacity product/price/payment link: **NOT CREATED**
- bank/procurement route for first buyer: **BUYER-SPECIFIC / UNKNOWN**
- payment received: **NO**

This does not block discovery, qualification, proprietary-data handoff, supplier onboarding, PO or signed commercial commitment. It blocks only a payment action that actually requires a presently unavailable correct rail.

## Market/compliance readiness

| Market | State | Boundary |
| --- | --- | --- |
| UK limited-company corporate routes | ACTIVE | sender identity + opt-out + suppression enforced |
| UK opt-out suppression | READY | Gmail label `Capacity Commitment/Do Not Contact` |
| Portugal | HOLD | DGC Article 13-B list/access response/check required |
| Spain | HOLD | LSSI lawful basis/route unresolved |

Owner authorization does not override a legal/compliance hold.

## Automation readiness

- hourly Capacity-only reply/bounce/opt-out/DGC condition watch: **ACTIVE**;
- non-binding buyer replies may be answered using the truth-safe response kit, with duplicate-response protection;
- binding/signature/settlement/legal-representation/payment-instruction requests: **ESCALATE, DO NOT BIND USER**;
- first-cohort follow-up: **2026-09-02 10:00 Europe/Lisbon**, conditional on continued silence and no suppression;
- Cohort 2: **2026-09-04 10:00 Europe/Lisbon**, conditional on no stronger T3 signal.

## Current critical path

1. **REAL BUYER RESPONSE / DELIVERY SIGNAL**
2. buyer-qualified bounded case and/or meaningful proprietary data
3. smallest credible costly commitment (priced pilot / signed engagement / qualified proprietary-data process)
4. correct procurement/payment rail when payment becomes due
5. execute bounded case → red-team → deliverable → buyer review
6. verify buyer economic outcome and our real revenue before T4

## Autonomous work exhaustion rule

Repository-safe preparation is considered exhausted only when:

- no known applicable P0/P1 remains in the bounded assisted journey;
- the latest material branch head has exact-head Python SUCCESS;
- buyer conversion copy/process exists;
- intake/confidentiality/payment boundaries exist;
- case execution/package/reporting/reopen flow is tested;
- current market continuation is scheduled/monitored;
- documentation and canonical baton reflect current product truth;
- remaining blockers require buyer/compliance/account evidence rather than speculative feature building.

Do **not** build automatic document extraction, broad SaaS workflows or portfolio features merely to avoid waiting for real T3 evidence. Reopen technical work immediately if a real case exposes a missing P0/P1 or delivery bottleneck.