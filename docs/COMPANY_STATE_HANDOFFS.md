# Q090 Company State — Integration / Golden Path / Sentinel handoffs

Canonical state: **QUEUED / PROTOTYPE prebuild**. PR: **#223**. No merge or production authorization.

## Integration Lab

### INT-Q090-01 — Requirements + Readiness
Combine current authorized base + Q090 #223 + Requirements #152 + Readiness #153 only after canonical dependency/merge-order gates permit it.

Acceptance:
1. known declared certification can be supplied as a fact, but Requirements owns whether it satisfies a named requirement;
2. absent certification remains UNKNOWN, never NOT_MET;
3. Company Profile country/region preferences remain `geography.preferred_*` and are excluded from the Requirements seam; they never prove operational geography;
4. `geography.operating_countries` stays UNKNOWN until supplied by an operational/trusted fact;
5. partial state does not produce READY through absence;
6. tenant A facts cannot enter tenant B assessment;
7. stale/conflicting company facts remain unknown/conflict at the Q090 boundary.

**Cross-cell bug:**

`BUG — Q090-INT-READINESS-001`

- OWNER: Readiness / PR #153
- MODULE/PR: `opportunity_readiness.py` / #153
- REPRO: pass a canonical Q090 operational state read model to the current `evaluate_readiness(..., company_state=...)` fallback path without an explicit `economic_fit_result`.
- EXPECTED CONTRACT: Readiness consumes Q090 operational facts through a public adapter and keeps legacy commercial profile/economic-fit input separate.
- OBSERVED: #153 currently uses the parameter both as tenant-bound “company state” and as the mapping passed into legacy `evaluate_economic_fit(...)`.
- IMPACT: semantic conflation; Q090 facts can be ignored/misinterpreted if wired directly. This is not a current production defect because both branches are non-canonical candidates.
- REQUIRED FIX: Readiness-owned integration adapter; do not modify Q090 into a profile-shaped compatibility object.

### INT-Q090-02 — Bid Economics
Combine Q090 #223 + Bid Economics #169 after queue authorization.

Acceptance:
- `finance.maximum_cash_exposure = EUR 50,000` is passed as a known constraint;
- an estimated opportunity exposure of EUR 70,000 remains a Bid Economics/decision-consumer calculation; Q090 emits no pursue/no-bid decision;
- absent or differently-currencied limits do not trigger silent FX/default EUR;
- Q090 and Bid Economics contract-local Money values translate through public `amount/currency` representations; neither capability imports the other's private Money class.

### INT-Q090-03 — MOBILIZE
Combine Q090 #223 + MOBILIZE #146 after queue authorization.

Acceptance:
- known owned van + unknown vehicle availability => Q090 adapter returns vehicle availability UNKNOWN;
- known `vehicle.available_count=0` => known zero;
- crew availability after its effective window => unavailable/unknown input, never extended;
- base location absent => UNKNOWN, not inferred from historic work regions or commercial market preferences.

### INT-Q090-04 — BANGS
Combine Q090 #223 + BANGS #195 when authorized.

Acceptance:
- equipment/capacity/base facts can seed the field-intelligence input seam;
- Q090 never manufactures supplier price, availability quote, tax, route or accommodation cost.

## Golden Path acceptance

Use synthetic/fixture data and label it accordingly.

1. **Small contractor / partial setup** — user gives services + preferred region only. Company State is useful immediately, preserves that region as a preference, and explicitly reports missing crew/vehicle/base/operating-country facts; no “complete profile” pressure.
2. **Preferred vs operational geography** — profile says Spain/Madrid. Requirements does not receive that as operating eligibility; `geography.operating_countries` remains UNKNOWN until separately attested.
3. **Known crew** — total 10, available 4 now. Consumers receive 4 available, not 10.
4. **Unknown crew** — total 10, available UNKNOWN. Consumers receive UNKNOWN.
5. **Zero crew** — available 0 explicitly. Preserve known zero.
6. **Known certification** — user declares ISO 9001. Preserve basis DECLARED and validity UNKNOWN unless supplied/verified.
7. **Unknown certification** — no record. Do not generate NOT CERTIFIED.
8. **Financial constraint** — declared EUR 50,000 exposure ceiling. Preserve Money/currency; no autonomous decision.
9. **Stale equipment/availability** — staleness visible; no assumption current.
10. **Conflicting observations** — preserve conflict until explicit supersession; a voluntary declaration cannot silently suppress a trusted fact.
11. **Tenant isolation** — A create/read/update/history; B cannot read/update/list A; forged account data has no authority.
12. **Legacy user** — old Company Profile continues functioning without mandatory Q090 form or migration.
13. **Provider/storage failure** — UI/consumer shows unavailable/unknown, not “no capacity”.

## Architecture Sentinel

Owner: `Q090_COMPANY_STATE_CONTRACT` / modules `company_state*.py`.

Public contract: `company-state.v1`.

Persistence: additive tenant-scoped `company_state_snapshots` in canonical SQLite connection; no second DB.

Tenant boundary: HTTP/application adapter must derive tenant from canonical auth; domain/service accepts trusted account id only.

Fitness opportunities / forbidden dependencies:
- Q090 domain must not import Requirements, Readiness, Bid Economics, MOBILIZE, BANGS or economic-fit internals;
- no client-controlled tenant id;
- manual/client facts cannot self-promote provenance, forge verification or suppress trusted facts;
- Company Profile market geography cannot become operational geography by projection;
- Requirements adapter must not emit `geography.preferred_*` as eligibility evidence;
- no eligibility/readiness/pursuit/action decision vocabulary or side effects;
- UNKNOWN must stay distinct from zero/false/negative;
- owned/employed must stay distinct from available;
- no default currency or FX;
- no bank/payroll/email/continuous GPS/surveillance requirement;
- no Q090 route/runtime registration while queue state remains QUEUED;
- no mutation of `master_execution_queue.py` or false capability promotion.

Rollback is bounded: revert Q090 code/docs/tests; no external services or production changes are introduced by PR #223.
