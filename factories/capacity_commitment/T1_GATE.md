# Capacity Commitment — T1 Gate Matrix

Decision state: **T1 — PILOT CAPABLE / HARDENED CONTINUATION VERIFIED**

Engine: `capacity-recoverability-t1.12`

Historical promotion evidence remains preserved: the original controlled assisted T1 candidate passed its promotion suite and established pilot capability. The later T2/T3 continuation has repeatedly reopened T1 whenever a new applicable P0/P1 was found, preserved failing-before evidence, repaired it, and required exact-head Python passing-after before returning to market work.

Latest validated code/test head before this documentation reconciliation:

- `996473147b623a677b6879fc028a5534db08017b`
- `ObraSignal Quality` run `33270658282`
- exact revision checkout: SUCCESS
- compile: SUCCESS
- repository Python suite: **949 passed / 2 skipped / 2 warnings**
- mobile: independent unrelated Expo dependency drift remains red; no whole-repository GREEN claim is made

Scope: controlled assisted automotive supplier volume-shortfall / dedicated-investment recoverability service. Manual contract review remains allowed. T1 remains create-only: a case cannot be silently edited or overwritten after creation.

## Minimum journey coverage

| Journey step | T1 implementation |
| --- | --- |
| Company | persisted `company_id` |
| Customer | persisted `customer_id` + `customer_matches` integrity gate |
| Program | persisted `program_id` + `program_matches` gate |
| Contract / nomination | at least one anchor required + `contract_matches`, `contract_current`, amendment gates |
| Commitment | explicit commitment state + committed units; zero-effective firm/flex commitment cannot become positive recoverability; forecast remains separate context |
| Capacity / investment | exposure type, cost mode, dedicated-asset and amortization verification |
| Forecast | persisted context only; forecast revision cannot alter firm committed units |
| Actual volume | completeness, deduplication, cancelled-order, unit, period and currency gates |
| Exposure | deterministic exact-Decimal calculation in an isolated fixed context; unsupported arithmetic range rejected |
| Mitigation | amount + explicit `mitigation_reviewed` gate |
| Prior recovery | amount + explicit `prior_recovery_reviewed` gate |
| Duplicate recovery | explicit `duplicate_claim_reviewed` gate + duplicate-claim block |
| Entitlement basis | explicit recovery right + contract/amendment integrity |
| Evidence | persisted evidence references; supported evidence cannot be asserted with zero references |
| Missing evidence | persisted separately and carried into next actions |
| Notice / deadline | validity + notice-window verification + canonical absolute deadline + assessment date; elapsed verified deadlines re-evaluate as expired |
| Recoverability | fail-closed engine; UNKNOWN and unsupported states are zero claimable |
| Claim / action package | self-validating truth-preserving package; never marks recovery/payment verified |
| Report | recomputes expected package from state and rejects stale/mutated truth |
| Save | validated source state only; exact material fields required at API boundary |
| Return | durable SQLite load/recompute under same engine version |
| State preserved | checksum + tenant binding + engine-version binding + exact schema-v2 field sets + canonical backup/restore |

## P0 gate

| P0 | Mechanism | Regression evidence | State |
| --- | --- | --- | --- |
| Fabricated contract right | recovery right is explicit; contract/amendment/customer integrity must be resolved; evidence refs required for supported evidence | oracle + E2E integrity cases | CLOSED IN ASSISTED SCOPE |
| Fabricated customer commitment | forecast separate from commitment; ambiguous/forecast-only/zero-effective commitment fail closed | oracle + forecast/commitment regressions | CLOSED |
| Fabricated payment/recovery | package hard-codes `verified_recovery=false`, `payment_received=false`; report rejects mutated package truth | package/report regressions | CLOSED |
| Cross-tenant leakage | tenant-scoped PK/load/list + provider identity | repository/web/E2E cross-tenant tests | CLOSED |
| Auth bypass | production runtime fixes provider JWT resolver and rejects unauthenticated development identity | auth/runtime tests | CLOSED |
| Destructive/corrupt persistence | checksummed exact-schema snapshots; restore validates canonical schema/rows before mutation and rejects same-file aliases | state/repository restore regressions | CLOSED |
| False recovery represented as verified | exposure/claimability/payment states distinct; external submission requires human review | package/report tests | CLOSED |

## P1 gate

| P1 | Mechanism | Regression evidence | State |
| --- | --- | --- | --- |
| Materially wrong capacity exposure | independent frozen oracle across full/minor/major/cancellation/direct-cost cases | `test_capacity_commitment.py` | CLOSED |
| Ambient Decimal changes result | fixed private Decimal context independent of caller precision/rounding/traps | decimal-determinism regressions | CLOSED |
| Out-of-range arithmetic escapes as runtime failure | Decimal arithmetic exceptions become deterministic invalid-input rejection | decimal-range web regression | CLOSED |
| Binary JSON float silently changes evidence value | financial/quantity boundary accepts exact decimal string or integer, rejects float | numeric-boundary regressions | CLOSED |
| Forecast treated as firm | forecast not used by engine; forecast-only is zero claimable | oracle + E2E forecast tests | CLOSED |
| Zero effective commitment treated as positive | FIRM/FLEX with zero committed units is non-recoverable for the volume-commitment wedge | zero-commitment regression | CLOSED |
| False definitive zero from uncertain inputs | zero-exposure integrity gate requires verification of the actual/amortization/mitigation/prior-recovery inputs that caused the zero | zero-truth regressions | CLOSED |
| Mitigation ignored/unreviewed | mitigation deducted before recoverability + `mitigation_reviewed` gate | oracle + direct/E2E tests | CLOSED |
| Prior recovery ignored/unreviewed | prior payment deducted + `prior_recovery_reviewed` gate | oracle + direct/E2E tests | CLOSED |
| Wrong amortization | `amortization_verified` gate | oracle + direct/E2E tests | CLOSED |
| Wrong contract | `contract_matches` + `contract_current` gates | oracle + E2E tests | CLOSED |
| Wrong amendment | amendment reviewed + applicable amendment match gates | oracle + E2E tests | CLOSED |
| Double recovery without review | `duplicate_claim_reviewed` must be true before positive position; known duplicate is non-recoverable | oracle + UI/web/package/report regressions | CLOSED |
| Notice validity goes stale with time | verified absolute deadline re-evaluated against explicit/UTC assessment date; expired => zero claimable | temporal/service/report regressions | CLOSED |
| Package direct-call bypass | package independently validates current evaluator result, evidence refs, deadline, assessment date and expiry consistency | package-boundary regressions | CLOSED |
| Lost evidence | evidence/missing-evidence refs in checksummed durable state and package/report | state/repository/package tests | CLOSED FOR ASSISTED REFERENCE-BASED T1 |
| Lost semantic snapshot field | schema-v2 top-level and nested `RecoveryCase` fields are exact; structurally changed re-signed payloads are rejected | state-schema strictness regressions | CLOSED |
| Unsafe/unreachable case identity | one URL-addressable case-ID policy enforced in web, repository, list/load and restore | case-ID regressions | CLOSED |
| Lost commitment history | create-only state; changed duplicate/concurrent create cannot overwrite first winner | sequential + concurrent repository tests | CLOSED |
| Required backup/restore failure | canonical columns/types/NOT-NULL/PK only; no unexpected trigger/index/FK; checksum/tenant/identity/version validation; row restore into live schema; hardlink/samefile aliases rejected | repository + restore-schema + samefile tests | CLOSED |
| Currency identity spoofing | three-letter ASCII alphabetic currency code required | currency regressions | CLOSED |

## Additional red-team coverage

Covered fail-closed/adversarial states now include wrong customer/program/period/currency/unit, missing or late call-off, duplicate volume, cancelled-order contamination, unverified asset dedication, shared capex, fully amortized tooling, mitigation reuse, prior payment, unreviewed duplicate search, notice-window uncertainty, deadline aging, expired claim right, superseded contract, stale same-ID package/result, package mutation, Markdown/source-text injection, binary float input, ambient Decimal context drift, arithmetic overflow, exact-state schema drift, invalid/unaddressable case IDs, retry after timeout, concurrent duplicate create, restart, backup, canonical restore and same-physical-file aliases.

Exact create replay is idempotent. A changed replay for the same tenant/case remains a conflict. This gives a safe recovery path after a client timeout without allowing overwrite.

## Verification boundary

`T1 — PILOT CAPABLE` does not mean commercial proof. The latest exact code/test head above is technical evidence only. Every later documentation/state successor must itself pass exact-head Python quality before it is treated as the current verified branch.

## Non-blocking post-T1 work

The following are deliberately **not T1 requirements** for this controlled assisted scope unless a real buyer/case exposes them as a P0/P1:

- automatic raw contract/document extraction;
- automatic page/line provenance extraction;
- mutable post-create editing/revision workflow;
- automated external submission;
- settlement/payment integration;
- production-hosted public/self-service deployment;
- real-customer commercial proof or WTP.

Building these merely to avoid waiting for buyer evidence would violate the T3 readiness discipline.

## External repository quality issue

The repository-wide mobile job remains red on an unchanged Expo/React Native dependency drift. Capacity Commitment does not modify mobile dependencies. This external red remains visible but is not evidence of a Capacity regression.

## T1 terminal rule

T1 remains valid while:

1. the final branch HEAD passes Capacity Commitment's Python quality suite;
2. no applicable known P0/P1 remains in the bounded assisted journey;
3. assisted scope remains create-only unless revision history is explicitly implemented;
4. the unrelated mobile failure is not misrepresented as green;
5. no merge or production deployment is implied by this terminal.

Any later applicable regression immediately reopens T1 and becomes ACTIVE before market progression continues.