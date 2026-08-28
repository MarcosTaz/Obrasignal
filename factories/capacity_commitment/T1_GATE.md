# Capacity Commitment — T1 Gate Matrix

Decision state: **T1 — PILOT CAPABLE**

Engine: `capacity-recoverability-t1.5`

Promotion evidence: exact candidate HEAD `bfeda970dfc9c7681d85d8a2afaccbc3dee6afe0` passed the full repository Python quality run with **855 passed / 2 skipped**. No applicable known P0/P1 remains in the controlled create-only assisted journey. This promotion does not imply merge, production deployment, market exposure, customer proof, settlement, payment, WTP, or revenue.

Scope: controlled assisted automotive supplier volume-shortfall / dedicated-investment recoverability service. Manual contract review remains allowed. T1 is create-only: a case cannot be silently edited or overwritten after creation.

## Minimum journey coverage

| Journey step | T1 implementation |
| --- | --- |
| Company | persisted `company_id` |
| Customer | persisted `customer_id` + `customer_matches` integrity gate |
| Program | persisted `program_id` + `program_matches` gate |
| Contract / nomination | at least one anchor required + `contract_matches`, `contract_current`, amendment gates |
| Commitment | explicit commitment state + committed units; forecast remains separate context |
| Capacity / investment | exposure type, cost mode, dedicated-asset and amortization verification |
| Forecast | persisted context only; forecast revision cannot alter firm committed units |
| Actual volume | completeness, deduplication, cancelled-order, unit, period and currency gates |
| Exposure | deterministic Decimal calculation |
| Mitigation | amount + explicit `mitigation_reviewed` gate |
| Entitlement basis | explicit recovery right + contract/amendment integrity |
| Evidence | persisted evidence references; supported evidence cannot be asserted with zero references |
| Missing evidence | persisted separately and carried into next actions |
| Notice / deadline | validity + notice-window verification + canonical absolute deadline |
| Recoverability | fail-closed engine; UNKNOWN and unsupported states are zero claimable |
| Claim / action package | truth-preserving package; never marks recovery/payment verified |
| Save | validated source state only |
| Return | durable SQLite load/recompute under same engine version |
| State preserved | checksum + tenant binding + engine-version binding + backup/restore |

## P0 gate

| P0 | Mechanism | Regression evidence | State |
| --- | --- | --- | --- |
| Fabricated contract right | recovery right is explicit, contract/amendment/customer integrity must be resolved, evidence refs required for supported evidence | oracle + E2E P1 gate cases | CLOSED IN ASSISTED SCOPE |
| Fabricated customer commitment | forecast is separate from commitment; ambiguous/forecast-only fail closed | forecast-only oracle + forecast-revision E2E tests | CLOSED |
| Fabricated payment | package hard-codes `verified_recovery=false`, `payment_received=false` | package + E2E tests | CLOSED |
| Cross-tenant leakage | tenant-scoped primary key/load/list + provider identity | repository/web/E2E cross-tenant tests | CLOSED |
| Auth bypass | production runtime fixes provider JWT resolver and rejects unauthenticated development identity | auth/runtime tests | CLOSED |
| Destructive corruption | checksummed snapshots; restore validates every row before live mutation | state/repository corruption tests | CLOSED |
| False recovery represented as verified | exposure/claimability/payment states are distinct; external submission requires human review | package tests | CLOSED |

## P1 gate

| P1 | Mechanism | Regression evidence | State |
| --- | --- | --- | --- |
| Materially wrong capacity exposure | independent frozen oracle across full/minor/major/cancellation/direct-cost cases | `test_capacity_commitment.py` | CLOSED |
| Forecast treated as firm | forecast not used by engine; forecast-only is zero claimable | oracle + E2E extreme/revised forecast tests | CLOSED |
| Mitigation ignored | mitigation deducted before recoverability + `mitigation_reviewed` gate | oracle + direct/E2E tests | CLOSED |
| Prior recovery ignored | prior payment deducted + `prior_recovery_reviewed` gate | oracle + direct/E2E tests | CLOSED |
| Wrong amortization | `amortization_verified` gate | oracle + direct/E2E tests | CLOSED |
| Wrong contract | `contract_matches` + `contract_current` gates | oracle + E2E tests | CLOSED |
| Wrong amendment | amendment reviewed + applicable amendment match gates | oracle + E2E tests | CLOSED |
| Double recovery | duplicate claim block; changed duplicate create conflicts | oracle + repository/web tests | CLOSED |
| Lost evidence | evidence/missing-evidence refs are in checksummed durable state and backup | state/repository/package tests | CLOSED FOR ASSISTED REFERENCE-BASED T1 |
| Lost commitment history | create-only state; changed duplicate/concurrent create cannot overwrite first winner | sequential + concurrent repository tests | CLOSED |
| Required backup/restore failure | validated SQLite backup/restore; corruption/version drift rejected before mutation | repository tests | CLOSED |

## Additional red-team coverage

Covered fail-closed states include wrong customer/program/period/currency/unit, missing or late call-off, duplicate volume, cancelled-order contamination, unverified asset dedication, shared capex, fully amortized tooling, mitigation reuse, prior payment, notice-window uncertainty, expired claim right, superseded contract, retry after timeout, concurrent duplicate create, restart, backup and restore.

Exact create replay is idempotent. A changed replay for the same tenant/case remains a conflict. This gives a safe recovery path after a client timeout without allowing overwrite.

## Non-blocking post-T1 work

The following are deliberately **not T1 requirements** for this controlled assisted scope:

- automatic raw contract/document extraction;
- automatic page/line provenance extraction;
- mutable post-create editing/revision workflow;
- automated external submission;
- settlement/payment integration;
- production market deployment;
- real-customer commercial proof or WTP.

Those belong to later product/market terminals unless evidence creates a new P0/P1.

## External repository quality issue

The repository-wide mobile job is currently red on an unchanged mobile dependency: Expo Doctor expects `react-native 0.86.3` while the existing mobile project pins `0.86.2`. Capacity Commitment does not modify mobile dependencies. This external red must remain visible but is not evidence of a Capacity Commitment domain regression.

## T1 terminal rule

T1 remains valid while:

1. the final branch HEAD continues to pass Capacity Commitment's Python quality suite;
2. no applicable P0/P1 is discovered;
3. assisted scope remains create-only unless revision history is explicitly implemented;
4. the unrelated mobile failure is not misrepresented as green;
5. no merge or production deployment is implied by this terminal.

Any later regression immediately reopens T1 and becomes ACTIVE before T2 work continues.
