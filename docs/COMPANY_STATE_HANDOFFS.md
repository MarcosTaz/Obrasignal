# Q090 Company State — Integration / Golden Path / Sentinel handoffs

Canonical state: **QUEUED / PROTOTYPE prebuild**. PR: **#223**. No merge or production authorization.

Public contract: `company-state.v1`.

## Integration Lab

### INT-Q090-00 — current main + Q090
First combination gate before downstream consumers.

Acceptance:
1. `master_execution_queue.py` remains untouched and Q080 stays canonical ACTIVE;
2. no Q090 API/UI/runtime route is registered;
3. Company Profile continues working independently;
4. fresh/existing/partial/repeated SQLite schema scenarios are safe;
5. tenant A current/history never appears under tenant B;
6. corrupt/incompatible storage fails explicitly rather than becoming an empty successful state.

### INT-Q090-01 — Requirements + Readiness
Combine current authorized base + Q090 #223 + Requirements #152 + Readiness #153 only after canonical dependency/merge-order gates permit it.

Acceptance:
1. known declared certification can be supplied as a fact, but Requirements owns whether it satisfies a named requirement;
2. absent certification remains UNKNOWN, never NOT_MET;
3. Company Profile country/region preferences remain `geography.preferred_*` and are excluded from the Requirements seam; they never prove operational geography;
4. `geography.operating_countries` stays UNKNOWN until supplied by an operational/trusted fact;
5. partial state does not produce READY through absence;
6. tenant A facts cannot enter tenant B assessment;
7. stale facts remain visible as stale/unknown and cannot override a separate current observation;
8. incompatible current facts remain CONFLICT;
9. scalar consumer envelopes preserve `knowledge_states` and `provenance_bases`; `KNOWN` means a usable value exists, not “externally verified FACT”.

**Cross-cell bug:**

`BUG — Q090-INT-READINESS-001`

- OWNER: Readiness / PR #153
- MODULE/PR: `opportunity_readiness.py` / #153
- REPRO: pass a canonical Q090 operational state read model to the current `evaluate_readiness(..., company_state=...)` fallback path without an explicit `economic_fit_result`.
- EXPECTED CONTRACT: Readiness consumes Q090 operational facts through a public adapter and keeps legacy commercial profile/economic-fit input separate.
- OBSERVED: #153 currently uses the parameter both as tenant-bound “company state” and as the mapping passed into legacy `evaluate_economic_fit(...)`.
- ROOT CAUSE: one Readiness parameter currently conflates operational-state context with a legacy commercial-profile-shaped economic-fit input.
- IMPACT: semantic conflation; Q090 facts can be ignored/misinterpreted if wired directly. This is not a current production defect because both branches are non-canonical candidates.
- REQUIRED FIX: Readiness-owned integration adapter; do not modify Q090 into a profile-shaped compatibility object.

### INT-Q090-02 — Bid Economics
Combine Q090 #223 + Bid Economics #169 after queue authorization.

Acceptance:
- `finance.maximum_cash_exposure = EUR 50,000` is passed as a company constraint;
- an estimated opportunity exposure of EUR 70,000 remains a Bid Economics/decision-consumer calculation; Q090 emits no pursue/no-bid decision;
- absent or differently-currencied limits do not trigger silent FX/default EUR;
- epistemic basis of an ESTIMATE/INFERENCE is preserved rather than upgraded to FACT;
- Q090 and Bid Economics contract-local Money values translate through public `amount/currency` representations; neither capability imports the other's private Money class.

### INT-Q090-03 — MOBILIZE
Combine Q090 #223 + MOBILIZE #146 after queue authorization.

Acceptance:
- known owned van + unknown vehicle availability => Q090 adapter returns vehicle availability UNKNOWN;
- known `vehicle.available_count=0` => known zero;
- total workers does not imply available workers;
- stale/future/expired crew availability is not current availability;
- a stale count does not poison a separate current count;
- base location absent => UNKNOWN, not inferred from historic work regions or commercial market preferences.

### INT-Q090-04 — BANGS
Combine Q090 #223 + BANGS #195 when authorized.

Acceptance:
- equipment/capacity/base facts can seed the field-intelligence input seam;
- stale/unknown facts retain their state;
- Q090 never manufactures supplier price, availability quote, tax, route or accommodation cost.

### INT-Q090-05 — OFFICE/Q120 trusted provider seam
Q090 already provides the narrow server-side target `CompanyStateService.ingest_trusted_facts`; Q120 provider/runtime implementation remains future work.

Acceptance:
1. tenant identity is supplied by trusted server/auth context, never provider payload authority;
2. provider facts require explicit `source_ref` and `observed_at`;
3. future `observed_at`/`verified_at` are rejected against the injected operation clock;
4. empty provider batches are not treated as evidence/successful observations;
5. provider cannot choose arbitrary supersession targets;
6. same source+basis+semantic fact may supersede only its own previous current observation;
7. different sources remain CONFLICT when incompatible; no universal hidden precedence;
8. manual facts cannot revoke/suppress trusted facts;
9. `LEARNED` remains `INFERENCE`, never FACT;
10. `UNAVAILABLE` remains UNKNOWN;
11. expected-version concurrency prevents silent lost writes;
12. identical same-clock provider replay is idempotent.

## Golden Path acceptance

Use synthetic/fixture data and label it accordingly.

1. **Realistic small contractor** — painting, Leiria base, 10 total workers, 6 available in a bounded window, one available vehicle, certification unknown, cash constraint unknown. Mobilize receives 6/1/base; Requirements sees the capability plus explicit unknown qualification; Economics receives UNKNOWN constraint and no decision.
2. **Minimal trade + base** — only drywall + Leiria base. Company State is valid; crew, vehicle and finance remain UNKNOWN to consumers; no “complete profile” pressure.
3. **Preferred vs operational geography** — profile says Spain/Madrid. Requirements does not receive that as operating eligibility; `geography.operating_countries` remains UNKNOWN until separately attested.
4. **Known crew** — total 10, available 4 now. Consumers receive 4 available, not 10.
5. **Unknown crew** — total 10, available UNKNOWN. Consumers receive UNKNOWN.
6. **Zero crew** — available 0 explicitly. Preserve known zero.
7. **Known certification** — user declares ISO 9001. Preserve basis DECLARED and validity UNKNOWN unless supplied/verified.
8. **Unknown certification** — no record. Do not generate NOT CERTIFIED.
9. **Financial constraint** — declared EUR 50,000 exposure ceiling. Preserve Money/currency and epistemic basis; no autonomous decision.
10. **Stale observation** — stale resource availability stays visible but is not current truth; a separate current observation may be used without a false conflict.
11. **Conflicting sources** — incompatible current manual/integration/registry observations remain conflict until explicit trusted resolution; no averaging.
12. **Learned observation** — future DNA signal remains INFERENCE.
13. **Tenant isolation** — A create/read/update/history/provider-ingest; B cannot read/update/list A; forged account data has no authority.
14. **Legacy user** — old Company Profile continues functioning without mandatory Q090 form or destructive migration.
15. **Provider/storage failure** — UI/consumer eventually translates failure to unavailable/unknown, not “no capacity”; Q090 itself raises controlled storage/provider validation errors.
16. **Replay** — same semantic state + same `as_of` is order-independent and fingerprint-stable; same provider fact + same clock does not inflate version history.

## Architecture Sentinel

Owner: `Q090_COMPANY_STATE_CONTRACT` / modules `company_state*.py`.

Public contract: `company-state.v1`.

Persistence owner: Q090 `company_state_store.py`, additive tenant-scoped `company_state_snapshots` in the caller-provided canonical SQLite connection; no second DB.

Tenant contract: future HTTP/application adapter derives tenant only from canonical auth; domain/service/provider seam receives a trusted account id and never treats payload/query headers as authority.

Protected fitness invariants:
- Q090 domain must not import Requirements, Readiness, Bid Economics, MOBILIZE, BANGS or economic-fit internals;
- no client-controlled tenant id;
- manual/client facts cannot self-promote provenance, forge verification or suppress trusted facts;
- provider facts require explicit source/observation evidence metadata and cannot select arbitrary supersession;
- cross-source disagreement has no hidden precedence and remains CONFLICT;
- `LEARNED` cannot be FACT; it remains INFERENCE;
- `UNAVAILABLE` cannot be a positive/negative fact; it remains UNKNOWN;
- stale observations are not current truth and do not create conflicts against usable current observations;
- Company Profile market geography cannot become operational geography by projection;
- Requirements adapter must not emit `geography.preferred_*` as eligibility evidence;
- scalar consumer adapters must preserve knowledge/provenance metadata;
- UNKNOWN stays distinct from zero/false/negative;
- owned/employed stays distinct from available;
- current factual available crew cannot exceed current factual total crew; stale/estimated totals do not manufacture a hard contradiction;
- no default currency, implicit EUR, silent FX or liquidity inference;
- incompatible/partial snapshot schema and corrupt persisted rows fail closed;
- material persistence failure rolls back open transactions;
- no bank/payroll/email/continuous GPS/surveillance requirement;
- no eligibility/readiness/pursuit/action decision vocabulary or external side effects;
- no Q090 route/runtime registration while queue state remains QUEUED;
- no mutation of `master_execution_queue.py` or false capability promotion.

Rollback is bounded: revert Q090 code/docs/tests. No external services, production changes or Master Queue changes are introduced by PR #223.
