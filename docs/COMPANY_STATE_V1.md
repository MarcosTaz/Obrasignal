# ObraSignal Company Operational State v1

Status: **Q090 prebuild / integration-ready candidate only**. Canonical queue state remains `QUEUED / PROTOTYPE`; this document does not promote Q090.

Contract: `company-state.v1`

## Purpose

Company State answers only: **what is this tenant's company currently known, assumed, estimated, or unknown to have or be able to execute?** It is a decision-support input contract. It is not Company Profile, ERP, eligibility, Readiness, Bid Economics, MOBILIZE, SHADOW, COMMAND or ACTION.

The product principle is permanent: **minimum data required, maximum intelligence extracted**. Company-level facts and voluntary inputs are sufficient for v1; no worker surveillance or invasive integration is required.

## Public model

`CompanyState` contains:
- trusted `account_id`;
- optional stable `company_ref`;
- timezone-aware `as_of`;
- append-only `state_version` assigned by persistence;
- deterministic `fingerprint` for lineage/replay/cache keys;
- bounded `facts`;
- explicit `unknowns`, `conflicts` and non-scoring quality counts.

A `CompanyFact` contains:
- `category` and stable extensible `code`;
- epistemic state: `FACT`, `ASSUMPTION`, `ESTIMATE`, `UNKNOWN`;
- `value` and optional unit/scope;
- provenance;
- `effective_from`, `effective_until`, `freshness_until` when relevant;
- explicit `supersedes` references.

Provenance basis is one of `DECLARED`, `PROFILE`, `VERIFIED`, `PUBLIC_REGISTRY`, `INTEGRATION`, `LEARNED`, `UNAVAILABLE`. `DECLARED` is legitimate evidence but is not external verification. `VERIFIED` requires a verification timestamp or evidence reference.

## Truth and unknown semantics

`UNKNOWN` always carries `value = null`. It is never serialized as zero, false, an empty negative assertion or a default currency.

Examples locked by tests:
- ten known employees does not imply ten available workers;
- no vehicle record does not mean zero vehicles;
- vehicle ownership does not imply availability;
- no ISO 9001 record does not mean not certified;
- an explicit zero available crew/vehicle count remains a known zero;
- stale/expired/future availability does not silently become current;
- two conflicting current values remain `CONFLICT` until explicit supersession resolves them.

V1 deliberately has **no universal source-precedence hierarchy**. A user declaration, registry observation and integration can each be relevant in context. Conflicting material facts remain visible instead of being averaged or silently overwritten.

## Time and freshness

All domain datetimes are timezone-aware and normalized to UTC. `as_of` is part of the fingerprint because operational truth is temporal.

- before `effective_from` => `NOT_YET_EFFECTIVE`;
- after `effective_until` => `EXPIRED`;
- after `freshness_until` => `STALE`;
- a temporal/verification anchor that remains valid => `CURRENT`;
- otherwise freshness is `UNKNOWN` rather than invented from retrieval time.

Effective interval endpoints are inclusive. Retrieval/storage time is not treated as proof of source freshness.

## Money

Decision-relevant financial constraints use Decimal-backed `Money(amount, currency)`. Currency is explicit; there is no default EUR and no FX conversion. NaN/Infinity and binary-float facts are rejected. Monetary operational limits are constraints only; Q090 never computes opportunity exposure or a pursue/no-bid decision.

The existing Company Profile `min_value`/`max_value` is intentionally not imported into financial capacity: it is a commercial target/preference and lacks the explicit currency/financial-capacity semantics required by Q090.

## Company Profile relationship

Company Profile remains the source of truth for relatively stable commercial identity/preferences. Q090 does not replace it.

`company_state_profile_adapter.py` is the single projection seam:
- non-empty services/tags -> `DECLARED` capability facts;
- recorded certifications -> `DECLARED_HELD`, validity `UNKNOWN`;
- explicit region/radius/countries -> declared geography where defensible;
- untouched legacy default `PRT` -> `ASSUMPTION`, not fact;
- profile-unmodeled crew availability/total, vehicle availability and base -> explicit `UNKNOWN` foundation facts.

Users do not need to complete those unknowns during generic onboarding. They are available for just-in-time acquisition when a real decision needs them.

## Persistence and history

Q090 uses the caller-provided canonical SQLite connection. It does not create another database or runtime.

`company_state_snapshots` is additive and append-only. Each tenant receives consecutive versions. The snapshot stores the validated public read model and deterministic fingerprint. Historical reads can therefore preserve the exact company context used by a later Decision/Evidence record.

Persistence rules:
- repeated schema initialization is safe;
- same consecutive semantic snapshot is idempotent;
- A -> B -> A remains three historical states when time/state materially changed;
- `BEGIN IMMEDIATE` + optimistic expected version prevents lost updates;
- storage corruption is an explicit error, never converted to an empty company;
- queries are tenant-scoped and parameterized;
- history reads are bounded.

This is snapshot history, not event sourcing.

## PATCH/application semantics

`CompanyStateService` accepts a **trusted** account id supplied by the caller's auth boundary. Client-controlled `account_id`, `tenant_id`, fingerprint, state version or contract metadata is forbidden.

For future transports:
- omitted field = leave existing field/facts unchanged, except omitted `as_of` uses the explicitly injected operation clock;
- `facts: null`, `revoke_fact_ids: null`, `as_of: null`, `expected_version: null` = invalid/ambiguous;
- adding `facts` is additive by deterministic fact id;
- a conflicting semantic fact is retained rather than overwriting another source;
- revocation/deletion of a voluntary fact is explicit by `revoke_fact_ids`;
- `company_ref: null` may explicitly clear the optional reference;
- expected version is optimistic concurrency; if omitted, the service binds the write to the exact snapshot it just read.

No HTTP endpoint is registered in this queued branch. A future HTTP adapter must derive tenant identity from canonical `configured_identity()` and may never authorize with payload/query tenant data.

## Consumer seams

`company_state_adapters.py` provides neutral public projections only:
- `requirements_facts`: capability/qualification/geography/capacity/equipment facts; Requirements owns MET/NOT_MET/UNKNOWN assessment.
- `readiness_inputs`: neutral state/facts/unknown/conflict envelope; Readiness owns readiness status.
- `economics_constraints`: known company financial limits only; Bid Economics owns opportunity calculations.
- `mobilize_inputs`: **available** workers, **available** own vehicles, base; ownership alone never populates availability.
- `bangs_inputs`: capacity/availability/equipment/geography/operational facts only; no price/cost observation is manufactured.

OFFICE/Q120 can later write validated facts through the same service/provider seam with explicit provenance and temporal bounds. No separate sensor database or plugin framework is needed.

## Failure semantics

No state row means Company State is not yet persisted; it does not assert that the company has zero capability. Corrupt/unreadable storage raises `CompanyStateStorageError`. Consumer integration should translate subsystem unavailability to explicit `UNKNOWN`/`UNAVAILABLE` according to the consumer's public contract, never to a favourable or negative fact.

## Security/privacy bounds

The domain bounds fact counts, string sizes, mappings, nesting and snapshot size. Invalid enum/code/date/currency, negative constrained quantities, binary floats, NaN/Infinity and control-character abuse fail closed. HTML-like strings remain data; this module renders no HTML. There is no network, secret, browser, shell or expression execution in the domain.

V1 stores company-level operational facts. It does not require bank/accounting/payroll/email/continuous location or employee productivity data. Future integrations must remain optional, purpose-bound, least-privilege, revocable and inspectable.

## Deliberate non-goals

Q090 does not provide:
- payroll, timesheets, HR or workforce surveillance;
- accounting, bank reconciliation, CRM or project management;
- inventory/fleet management;
- opportunity requirements extraction;
- eligibility/readiness/pursuit decisions;
- bid/working-capital formulas;
- mobilization cost calculation;
- supplier/hotel/equipment prices;
- portfolio optimization;
- external actions.

## Current integration limitation

Readiness PR #153 currently names a legacy profile-like mapping `company_state` and may pass it to `economic_fit.evaluate_economic_fit`. A canonical `company-state.v1` object must **not** impersonate that legacy commercial profile. Integration Lab should update the Readiness-owned adapter so Q090 operational facts and commercial profile/economic-fit inputs remain separate.

## Rollback

Before merge: close PR #223/delete the feature branch. If an authorized future merge occurs, revert Q090 runtime/test/doc commits. The additive snapshot table can remain inert; destructive table/data removal requires a separately reviewed retention/migration decision.
