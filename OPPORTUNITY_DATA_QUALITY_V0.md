# ObraSignal Opportunity Data Quality / Completeness v0

**Status:** IMPLEMENTED on isolated feature branch; not merged and not production-promoted.  
**Contract:** `opportunity-data-quality.v0`

## PURPOSE

Answer one bounded question:

> **How much do we actually know about this opportunity record?**

The capability evaluates canonical/normalized opportunity or Signal data and reports what is available, missing, explicitly unknown, invalid, stale under an explicit policy, not applicable, or structurally not provided by the publisher.

It is intentionally conservative. Missing information is itself useful information.

## NON-GOALS

Data completeness is **not**:

- commercial opportunity quality;
- relevance to a company;
- probability of winning;
- recommendation confidence;
- economic fit;
- bid/readiness or eligibility;
- connector/source health;
- automatic enrichment;
- an Evidence Graph;
- a machine-learning prediction.

A record can be 100% complete and commercially unattractive. A sparse record can describe an excellent opportunity. The evaluator produces no commercial score, confidence score, GO/NO-GO result or recommendation.

## ARCHITECTURE

V0 is an on-demand pure evaluator over a `Mapping`. It owns no persistence, migration, background job, network client or model call. It does not mutate the canonical Opportunity/Signal.

This follows the modular-monolith contract: source-native schemas are normalized before product logic, and capability-private storage is not read directly. Optional source knowledge is supplied through the small `source_context` contract.

`procurement_quality.py` remains responsible for conservative procurement identity/deduplication helpers. `source_health.py` remains responsible for connector execution health and freshness SLA. Neither is redefined here.

## FIELD REGISTRY

`FIELD_REGISTRY` is the single registry for v0. Adding an evaluated canonical field requires a registry entry and tests, not scattered conditionals.

| Key | Meaning | Critical | Notes |
| --- | --- | --- | --- |
| `source` | canonical source identity | yes | non-empty identifier |
| `opportunity_identity` | `external_id` or canonical opportunity id | yes | non-empty identifier |
| `title` | opportunity title | yes | usable text |
| `buyer` | contracting buyer | no | usable text |
| `location` | canonical place or country | no | usable text |
| `deadline` | response/tender deadline | no | applicable by signal type/policy; valid datetime |
| `published_value` | published monetary value | no | non-negative parseable monetary value |
| `currency` | separate currency field | no | evaluated only when represented/expected |
| `description` | normalized description | no | usable text |
| `category` | category code, CPV or taxonomy | no | usable canonical classification |
| `publication_date` | publication timestamp/date | no | valid datetime/date |
| `provenance` | source reference or source URL | yes | usable reference/HTTP(S) URL |
| `updated_at` | source/record update timestamp | no | evaluated only when represented/expected; optional freshness rule |

The registry is deliberately small. Documents, requirements and richer evidence are not inferred from private or unavailable modules.

## AVAILABLE / MISSING / UNKNOWN / INVALID

### AVAILABLE

A field is `AVAILABLE` only when it exists and is semantically usable. Blank text, empty containers and invalid values are not available.

### MISSING

`MISSING` means the field is expected and applicable but was not supplied. A missing value is never silently enriched.

### UNKNOWN

`UNKNOWN` is distinct from missing. It is used only when `source_context.unknown_fields` explicitly states that the system cannot determine the field state/value correctly. Unknown fields remain in the completeness denominator and never count as available.

### INVALID

`INVALID` means a supplied value fails a deterministic field validator, for example a malformed date, malformed currency representation, negative monetary value, unsafe NUL-containing text or unusable identifier. Invalid is never converted to missing.

### STALE

`STALE` is used only for a registered freshness timestamp when the caller supplies an explicit `DataQualityPolicy(stale_after_days=...)`. V0 does not import connector health or assume that a record is stale merely because it is several days old.

Stale data is still *present*, so it remains in the numerator for data completeness while being separately exposed in `stale_fields`. This keeps presence and freshness as separate dimensions.

## APPLICABILITY

Not every canonical field applies to every Signal type.

V0 examples:

- deadline is expected for `TENDER` and `FORECAST` records;
- deadline is `NOT_APPLICABLE` to another Signal type unless the source contract explicitly lists it in `expected_fields`;
- a separate currency field is evaluated only when the record represents it or the source contract expects it;
- update timestamp is evaluated only when represented or explicitly expected.

`NOT_APPLICABLE` fields are excluded from the denominator.

## COMPLETENESS CALCULATION

V0 uses an unweighted, auditable ratio:

`present applicable fields / applicable expected fields`

Where:

- numerator = `AVAILABLE + STALE`;
- denominator = `AVAILABLE + MISSING + UNKNOWN + INVALID + STALE`;
- `NOT_APPLICABLE` is excluded;
- `NOT_PROVIDED_BY_SOURCE` is excluded.

The ratio is rounded to four decimal places. No importance weighting or magic quality score is applied.

Example: 8 present fields among 10 applicable expected fields = `0.8` data completeness. It does **not** mean 80% confidence or an 80/100 commercial opportunity.

## SOURCE LIMITATIONS

A publisher may structurally omit a field. `source_context.not_provided_fields` represents that distinction explicitly as `NOT_PROVIDED_BY_SOURCE`.

Such a field is excluded from the denominator because its absence should not create the false impression that an ingestion connector failed. `source_coverage_notes` may explain the limitation. Notes are bounded and sanitized for safe read-model output.

V0 does not maintain a global publisher-field matrix. That would require evidence for each source and is future integration work, not something to invent in this module.

## PROVENANCE

Material data should retain a usable source reference where the canonical contract provides one. V0 evaluates `source_reference` or `url` as a small provenance-presence check. It does not build or query the Evidence Graph.

## FRESHNESS

Record freshness is opt-in and policy-driven. The only v0 freshness-capable field is the canonical source/record update timestamp. The evaluator requires:

1. an applicable timestamp;
2. a valid timestamp value;
3. an explicit `stale_after_days` policy;
4. an explicit evaluation clock for reproducible freshness tests/evaluations.

Source connector health remains the responsibility of `source_health.py`.

## SERVICE CONTRACT

```python
evaluate_opportunity_data_quality(
    opportunity,
    source_context,
    policy,
    evaluated_at=clock,
) -> OpportunityDataQuality
```

The evaluation is deterministic for the same opportunity, source context, policy and evaluation clock. Passing the clock explicitly is required for reproducible comparisons whenever generated timestamps/freshness matter.

The return model exposes:

- available;
- missing;
- unknown;
- invalid;
- stale;
- critical missing;
- not applicable;
- structurally not provided by source;
- completeness ratio;
- policy version;
- generated timestamp;
- bounded source-coverage notes.

## API

No HTTP route is added in v0 on this branch.

**Decision:** the repository already has a stable `/api/v1/opportunities/{id}` read model, but the completeness evaluator can be independently tested and integrated later without coupling it prematurely to the legacy `tenders` transport projection. An API adapter should be a small follow-up once the canonical Signal/Opportunity read-model source for all signal types is settled.

A compatible future shape is:

`GET /api/v1/opportunities/{id}/data-quality`

It should serialize `OpportunityDataQuality.to_dict()` and use only public canonical/source-metadata interfaces.

## UI

No UI/dashboard is added in v0. This avoids increasing product surface before the read model is integrated.

Future copy should be literal and non-commercial, for example:

- `Data quality: good coverage`
- `Missing: published value`
- `Unknown: latest document revision`

Never: `This opportunity is low quality.`

Labels must carry meaning independently of color.

## SECURITY

The evaluator:

- performs no SQL and therefore adds no SQL-injection surface;
- performs no HTML rendering;
- makes no external requests;
- rejects malformed canonical values rather than coercing them to available;
- rejects NUL-containing identifiers/text;
- bounds source-coverage notes to 20 entries × 1,000 characters;
- does not consume company-private enrichment, so v0 output is not tenant-specific;
- does not log raw source payloads or secrets.

If private tenant enrichment is introduced later, the assessment must become explicitly tenant-scoped and isolation-tested.

## TESTS

`test_opportunity_data_quality.py` covers:

- fully populated, partial and nearly empty records;
- blank/missing values;
- applicability and `NOT_APPLICABLE` denominator behavior;
- `UNKNOWN` versus `MISSING`;
- `INVALID` versus `MISSING`;
- malformed date/currency, negative money and unsafe strings;
- critical missing fields;
- transparent completeness calculation;
- source structural limitations;
- missing provenance;
- different Signal types;
- explicit expected-field overrides;
- no mutation of inputs;
- deterministic replay with a fixed clock/policy;
- policy-driven freshness;
- bounded metadata notes;
- monotonic completeness properties;
- absence of confidence/commercial score claims.

Repository-wide CI remains the integration quality gate.

## KNOWN LIMITATIONS

- V0 intentionally evaluates a small canonical field set rather than every source-specific attribute.
- Source structural limitations must be supplied explicitly; the module does not invent them.
- Currency validation checks canonical form rather than maintaining an ISO-4217 reference database.
- No document inventory, requirements, readiness or Evidence Graph integration is assumed because those contracts are not currently present as integrated public modules on the inspected `main` baseline.
- No persistence/snapshot history is created.
- No API/UI integration is claimed.

## FUTURE INTEGRATIONS

Not implemented in v0:

- canonical HTTP adapter after the cross-signal Opportunity read model is settled;
- public Document Inventory coverage when its contract exists;
- public Requirements-known/unknown coverage without eligibility scoring;
- Evidence Graph presence checks through its versioned public contract;
- source-specific publication-limit policies backed by evidence;
- snapshot comparison across `policy_version` values;
- safe tenant-specific enrichment quality with isolation controls.

Automatic enrichment, web research, LLM filling, source repair, commercial scoring, probability of win, Readiness, COMMAND recommendation logic, global source-health replacement and ML quality prediction remain explicitly out of scope.

## INTEGRATION / ROLLBACK

The module is isolated: integration is an import plus adapter; rollback is removal of the evaluator/tests/docs. There is no schema migration, persisted state, queue change or external dependency to unwind.

This parallel implementation does not modify `CURRENT_ITEM_ID`, reorder or mark any Master Execution Queue capability as done, promote Readiness/COMMAND, or merge itself.
