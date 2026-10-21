# ObraSignal Company Operational State v1

Status: **Q090 prebuild / integration-ready candidate only**. Canonical queue state remains `QUEUED / PROTOTYPE`; this document does not promote Q090 and authorizes no merge or deployment.

Contract: `company-state.v1`

## Purpose

Company State answers only: **what is this tenant's company currently known, assumed, estimated, inferred, or unknown to have or be able to execute?** It is a decision-support input contract. It is not Company Profile, ERP, eligibility, Readiness, Bid Economics, MOBILIZE, SHADOW, COMMAND or ACTION.

The permanent product principle is **minimum data required, maximum intelligence extracted**. Company-level facts and voluntary inputs are sufficient for v1; no bank, payroll, email, continuous GPS or employee-surveillance integration is required.

## Public model

`CompanyState` contains:
- trusted `account_id`;
- optional stable `company_ref`;
- timezone-aware `as_of`;
- append-only `state_version` assigned by persistence;
- deterministic tenant-aware `fingerprint` for lineage/replay/cache keys;
- bounded `facts`;
- explicit `unknowns`, `conflicts` and non-scoring epistemic quality counts.

A `CompanyFact` contains:
- category and stable extensible code;
- epistemic state: `FACT`, `ASSUMPTION`, `ESTIMATE`, `INFERENCE`, `UNKNOWN`;
- value and optional unit/scope;
- provenance;
- `effective_from`, `effective_until`, `freshness_until` when relevant;
- explicit `supersedes` references.

Provenance basis is one of `DECLARED`, `PROFILE`, `VERIFIED`, `PUBLIC_REGISTRY`, `INTEGRATION`, `LEARNED`, `UNAVAILABLE`. `DECLARED` is legitimate evidence but is never external verification. `VERIFIED` requires a verification timestamp or evidence reference. `LEARNED` can only represent `INFERENCE`; it cannot masquerade as `FACT`. `UNAVAILABLE` can only represent `UNKNOWN`.

## Truth and UNKNOWN semantics

`UNKNOWN` always carries `value = null`. It is never serialized as zero, false, an empty negative assertion or a default currency.

Tests lock the following distinctions:
- ten known employees does not imply ten available workers;
- no vehicle record does not mean zero vehicles;
- vehicle ownership does not imply availability;
- no ISO 9001 record does not mean not certified;
- explicit zero available crew/vehicle count remains a known zero;
- stale/expired/future availability does not silently become current;
- a stale observation remains visible but does not override or conflict with a usable current observation;
- two incompatible **current** values remain `CONFLICT` until explicit supersession resolves them;
- estimates, assumptions and learned inferences are never counted as `FACT` merely because they have a value.

V1 deliberately has **no universal source-precedence hierarchy**. User declarations, registries and integrations can each be relevant. Material current disagreement remains visible instead of being averaged or silently overwritten.

## Time, freshness and temporal supersession

All domain datetimes are timezone-aware and normalized to UTC. `as_of` participates in the fingerprint because operational truth is temporal.

- before `effective_from` => `NOT_YET_EFFECTIVE`;
- after `effective_until` => `EXPIRED`;
- after `freshness_until` => `STALE`;
- a valid temporal/verification anchor => `CURRENT`;
- otherwise => `UNKNOWN` freshness.

Effective interval endpoints are inclusive. Retrieval/storage time is not treated as proof of source freshness. `active_facts()` retains stale observations for explainability/unknown reporting; `current_facts()`, current-value resolution and conflict detection exclude stale observations.

Supersession is also time-aware. A future-dated replacement does **not** hide the prior current fact before the replacement reaches `effective_from`. Once the replacement becomes effective, its supersession remains authoritative even after that replacement later becomes stale or expires; historical truth is not silently resurrected as present truth.

## Money

Decision-relevant financial constraints use Decimal-backed `Money(amount, currency)`. Currency is explicit; there is no default EUR and no FX conversion. Binary float, NaN and Infinity are rejected for authoritative monetary facts. Malformed serialized monetary amounts fail through the Company State contract error rather than leaking a lower-level Decimal parser exception.

The existing Company Profile `min_value`/`max_value` is intentionally **not** imported as financial capacity: it is a commercial target/preference and lacks explicit currency/capital-capacity semantics. Q090 exposes constraints only; Bid Economics owns opportunity exposure and financial calculations.

There is currently no canonical Money type on `main`. Parallel Bid Economics PR #169 has its own contract-local Money. If both are later integrated, translate via their public amount/currency representations rather than importing either module's private Money implementation into the other.

## Company Profile relationship

Company Profile remains the source of truth for relatively stable commercial identity/preferences. Q090 does not replace it and does not reinterpret preferences as execution truth.

`company_state_profile_adapter.py` is the single projection seam:
- non-empty services/tags -> `DECLARED` capability facts;
- recorded certifications -> `DECLARED_HELD`, validity `UNKNOWN`;
- profile countries -> `geography.preferred_countries`, never `operating_countries`;
- profile regions -> `geography.preferred_regions`, never operational jurisdiction proof;
- untouched legacy default `PRT` -> preferred-country `ASSUMPTION`, not operational fact;
- explicit `geographic_radius_km` -> declared `geography.practical_radius_km` because the existing UI labels this as an operational radius;
- profile-unmodeled crew total/availability, vehicle availability, base and operating countries -> explicit `UNKNOWN` foundation facts.

A preference such as “look for work in Spain” therefore cannot silently become “the company is operationally able/registered/willing to execute in Spain”. `requirements_facts()` deliberately excludes `geography.preferred_*` so a market preference cannot satisfy an eligibility/geography requirement.

Users do not need to fill these unknowns during generic onboarding. They are suitable for just-in-time acquisition when a real decision needs them.

## Persistence and history

Q090 uses the caller-provided canonical SQLite connection. It does not create another database or runtime.

`company_state_snapshots` is additive and append-only. Each tenant receives consecutive versions. A snapshot stores the validated public read model and deterministic fingerprint so later Decision/Evidence lineage can preserve the company context used at decision time.

Persistence rules:
- repeated schema initialization is safe;
- existing unrelated DB content is preserved;
- a pre-existing partial/incompatible `company_state_snapshots` table fails closed instead of being treated as migrated;
- the `(account_id, state_version)` uniqueness invariant is verified, not assumed from column names;
- same consecutive semantic snapshot is idempotent;
- A -> B -> A remains historical when time/state materially changed;
- `BEGIN IMMEDIATE` + optimistic expected version prevents lost updates;
- row query metadata must match snapshot JSON version/fingerprint/contract/as-of;
- corrupt storage is an explicit error, never an empty company state;
- persistence errors after transaction start roll back before propagating;
- queries are tenant-scoped and parameterized;
- history reads are bounded.

This is snapshot history, not event sourcing.

## Voluntary PATCH/application semantics

`CompanyStateService` accepts a **trusted** account id supplied by the caller's auth boundary. Client-controlled `account_id`, `tenant_id`, fingerprint, state version or contract metadata is forbidden.

The public application `patch()` seam is specifically the **voluntary/manual** input boundary:
- voluntary facts are server-labelled `DECLARED` with source `manual`;
- the client cannot self-promote a fact to `VERIFIED`, `PUBLIC_REGISTRY`, `INTEGRATION`, `LEARNED` or `PROFILE`;
- the client cannot forge `verified_at`, evidence refs, observation time or source identity;
- the client cannot select supersession targets;
- a newer manual declaration supersedes only the current manual declaration of the same semantic fact;
- a manual declaration never silently supersedes a trusted provider/registry/verified fact; disagreement remains `CONFLICT`;
- voluntary revocation can remove only voluntary manual facts and cannot hide trusted facts;
- revoking the newest manual declaration removes its manual supersession chain from the current snapshot, so an older revoked value cannot silently reappear; historical snapshots remain immutable;
- duplicate semantic keys in one patch are rejected instead of last-write-wins.

PATCH field semantics:
- omitted field = leave state unchanged, except omitted `as_of` uses the explicitly injected operation clock;
- `facts: null`, `revoke_fact_ids: null`, `as_of: null`, `expected_version: null` = invalid/ambiguous;
- `company_ref: null` may explicitly clear the optional reference;
- expected version is optimistic concurrency; when omitted, the service binds the write to the exact snapshot it just read.

## Trusted OFFICE/provider ingestion seam

`CompanyStateService.ingest_trusted_facts()` is the narrow server-side target for future OFFICE/Q120, official-registry and verified-integration observations. It is deliberately **not** a generic provider framework and registers no new runtime.

Rules:
- tenant identity is a trusted server argument, not provider/client payload authority;
- input values must already be validated `CompanyFact` objects;
- accepted provider bases are `VERIFIED`, `PUBLIC_REGISTRY`, `INTEGRATION`, `LEARNED`, `UNAVAILABLE`;
- every provider fact requires explicit `source_ref` and `observed_at`;
- `observed_at` and `verified_at` cannot be in the future relative to the injected operation clock;
- an empty batch is not treated as successful evidence;
- providers cannot select arbitrary supersession targets;
- the server supersedes only the previous current observation with the same semantic key, provenance basis and source identity;
- a different source does not silently replace another source; incompatible current observations remain `CONFLICT`;
- learned provider values remain `INFERENCE`, never `FACT`;
- expected-version semantics prevent stale/lost provider writes;
- same fact + same clock replay is idempotent and preserves the same snapshot version/fingerprint.

No HTTP endpoint is registered in this queued branch. A future HTTP adapter must derive tenant identity from canonical `configured_identity()` and may never authorize with payload/query tenant data.

## Consumer seams

`company_state_adapters.py` provides neutral public projections only:
- `requirements_facts`: operational capability/qualification/geography/capacity/equipment facts; excludes `geography.preferred_*`; Requirements owns MET/NOT_MET/UNKNOWN assessment.
- `readiness_inputs`: neutral state/facts/unknown/conflict envelope; Readiness owns readiness status.
- `economics_constraints`: company financial constraints only; Bid Economics owns opportunity calculations.
- `mobilize_inputs`: **available** workers, **available** own vehicles and base; ownership alone never populates availability.
- `bangs_inputs`: capacity/availability/equipment/geography/operational facts only; no price/cost observation is manufactured.

Scalar consumer envelopes expose `KNOWN`/`UNKNOWN`/`CONFLICT` as **value usability**, while also carrying `knowledge_states` and `provenance_bases`. Therefore an `ESTIMATE`, `ASSUMPTION` or `INFERENCE` can be transported without being relabelled as verified `FACT`. A stale source cannot poison a separate current observation of the same semantic fact.

The machine-readable Integration Manifest contains the field-to-consumer matrix and makes all of these downstream dependencies optional. Consumers must not read private Q090 storage, invent zero from missing data, mutate Company State during evaluation or create facts on Q090's behalf.

## Failure semantics

No state row means Company State is not yet persisted; it does not assert zero capability. Corrupt/unreadable/incompatible storage raises `CompanyStateStorageError`. Provider absence must be represented as explicit `UNAVAILABLE`/`UNKNOWN` data when material; an empty provider batch is not evidence. Consumer integration should translate subsystem failure to explicit `UNKNOWN`/`UNAVAILABLE` according to the consumer's public contract, never to a favourable or negative fact.

## Security/privacy bounds

The domain bounds fact counts, string sizes, mappings, nesting and snapshot size. Invalid enum/code/date/currency, negative constrained quantities, binary floats, NaN/Infinity and C0 control-character abuse fail closed. HTML-like strings remain data; Q090 renders no HTML. There is no network, secret, browser, shell or expression execution in the domain.

V1 stores company-level operational facts. It does not require bank/accounting/payroll/email/continuous location or employee productivity data. Future integrations must remain optional, purpose-bound, least-privilege, revocable and inspectable.

## Product acceptance

Executable acceptance fixtures demonstrate both:
1. a realistic small contractor with trade, base, 10 total workers, 6 available workers in a bounded window, one available vehicle, unknown certification and unknown cash constraint; and
2. a minimal contractor with only trade + base, where crew/equipment/finance remain unknown to consumers without forcing a giant onboarding form.

The same semantic state at the same `as_of` remains order-independent and fingerprint-stable.

## Deliberate non-goals

Q090 does not provide payroll, HR, accounting, CRM, project management, inventory/fleet management, Requirements extraction, eligibility/readiness/pursuit decisions, bid formulas, mobilization calculations, supplier/hotel/equipment prices, portfolio optimization or external actions.

## Current integration limitation

Readiness PR #153 currently names a legacy profile-like mapping `company_state` and may pass it to `economic_fit.evaluate_economic_fit`. A canonical `company-state.v1` object must **not** impersonate that legacy commercial profile. Integration Lab should update the Readiness-owned adapter so Q090 operational facts and commercial profile/economic-fit inputs remain separate.

## Rollback and queue boundary

Before merge: close PR #223/delete the feature branch. If an authorized future merge occurs, revert Q090 runtime/test/doc commits. The additive snapshot table can remain inert; destructive table/data removal requires a separately reviewed retention/migration decision.

Q080 remains the active Master Queue item and Q090 remains `QUEUED / PROTOTYPE`. **No automatic merge. No production mutation. No Master Queue promotion.**
