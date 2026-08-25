# France procurement coverage — BOAMP + DECP evidence

Date: 2026-08-25  
Integration branch: `integration-international/france-decp-current-main-20260825`  
Source implementation provenance: PR #171 / `e8209221d21d30f009021f3088df8c0a172a78d7`  
Current-main reconciliation base: `fce51d5b5524e09691f9187f7619ea0166217487`  
Canonical market classification: `BUILD` (unchanged)  
Master Execution Queue: not modified.

## Executive decision

France remains a high-value BUILD market, but the rational unit of coverage is a two-source official family rather than a new all-purpose bespoke portal connector:

- **BOAMP** remains the existing tender/discovery layer already wired in ObraSignal.
- **DECP** is added as the official post-award/contract intelligence layer, emitting canonical `CONTRACT` signals only.
- **TED/eForms** remains complementary EU coverage; it is not treated as a substitute for national DECP contract depth.

This integration candidate does not mark France or DECP as production-deployed. `FR_DECP` is registry `ready` and runtime-gated. Ingestion requires explicit inclusion in `OBRASIGNAL_GLOBAL_SOURCES`, merge, deployment, and normal production verification.

## Commercial case

France is already a canonical BUILD market in `market_scope_registry.py`, with strong demand intensity, construction relevance and monetization potential. The incremental engineering cost is justified because DECP adds buyer/supplier/contract-value/history evidence that tender-only coverage cannot provide.

The market is competitive, not empty. Publicly visible French products observed during the source assessment reinforced that generic tender alerts are commoditized; ObraSignal should differentiate through construction-specific decision intelligence, lifecycle evidence and contractor fit rather than merely republishing notices.

**Go-to-market signal:** `GOOD SCALE MARKET`.

## Source landscape

### BOAMP — discovery / notices

Publisher: Direction de l'information légale et administrative (DILA) / BOAMP.  
Access: official public open-data API / downloadable open data.  
Rights: Licence Ouverte / Open Licence.  
Observed publication cadence: BOAMP states the data are published twice daily, seven days a week.  
Role in ObraSignal: tender/discovery source already present as `BOAMP`.

Signal types supported in current ObraSignal mapping:

- `TENDER`

This integration deliberately does not duplicate or rewrite the existing BOAMP connector.

### DECP — contracts / post-award intelligence

Publisher: Direction des Affaires juridiques (DAJ), French Ministry of Economy.  
Dataset: `decp-2022-marches-valides`.  
Portal: `https://www.data.economie.gouv.fr/explore/dataset/decp-2022-marches-valides/`  
Machine endpoint: Opendatasoft/Huwise Explore API v2.1 `records`.  
Geographic coverage: France entière in the official dataset metadata.  
Observed dataset cadence: daily.  
Rights: Licence Ouverte / Open Licence v2.0.  
Authentication: none for the public Explore API used here.

Signal types implemented:

- `CONTRACT`

Useful native fields include procurement/contract identifier, object, CPV, procedure, buyer identity, supplier identity, amount, notification/publication dates, place of execution and modification fields.

## Construction filter

Primary filter: publisher-native CPV division `45` (construction work).

The connector applies the filter twice:

1. server-side `startswith(codecpv, "45")` to bound transfer and processing;
2. local validation that normalized CPV begins with `45`, so a server/filter regression cannot admit unrelated records.

No keyword-only construction classification is used.

## Identity and update semantics

Canonical source identity is DECP `id`.

If the same contract ID is re-observed with changed data, the connector keeps the same `external_id`; canonical Signal upsert therefore updates the same identity instead of creating a duplicate. Where a parseable modification publication/notification date is present on the record, it can contribute to that record's `source_updated_at`.

Incremental discovery itself is deliberately narrower. The current DECP 2022 schema exposes its modification-publication field as text, so this connector uses the original `datepublicationdonnees` date as its safe server-side cursor with a small overlap. It therefore **does not claim complete incremental capture of amendments to old contracts**.

A bounded live query probe on 2026-08-25 confirmed the actual DECP endpoint semantics: CPV `startswith` works, quoted ISO date comparison works (`datepublicationdonnees >= 'YYYY-MM-DD'`), while `date:` casts are rejected by the dataset's live ODSQL parser.

Canonical storage primary key `(source, signal_type, external_id)` makes repeat ingestion idempotent and allows re-observed DECP versions to update the same contract signal.

## Freshness and historical utility

- BOAMP: twice-daily publisher cadence; discovery use.
- DECP: daily dataset cadence; contract/history use.
- DECP provides materially better historical buyer/supplier/contract-value evidence than tender notices alone and is therefore useful for Buyer Intelligence, competitor intelligence, benchmarking and future contract-expiry analysis when the canonical lineage/term evidence supports it.

No claim is made that DECP is a real-time award source, that an award equals a contract, or that contract history proves a future replacement procurement.

## Technical access and safety

Connector: `france_decp.py`.

Controls:

- explicit HTTP timeout;
- bounded retries;
- 429 and 5xx retry handling, with bounded `Retry-After` respect;
- bounded page size and maximum page count;
- pagination-cap failure is an error, not a false success;
- malformed response schema fails closed;
- malformed construction records with missing identity/update date fail closed before cursor advancement;
- publisher HTTPS URL allow-list prevents arbitrary record URLs becoming trusted outbound links;
- source content is normalized rather than persisted as unrestricted raw publisher payload;
- cursor is publisher-derived, not wall-clock-success-derived.

## Runtime and architecture

`france_runtime.py` uses the existing `incremental_runtime_plugin` and therefore follows the canonical staged source transaction.

Because DECP is `CONTRACT`, the runtime stages it to canonical Signal persistence and does not project it into the legacy `tenders` table. Product business logic remains outside the connector.

The original source PR used a small `france_app.py` wrapper and changed Render to start `france_app:APP`. The international consolidation rejected that extra composition root even though it reused the same Flask object. The reconciled implementation instead keeps the existing production WSGI boundary unchanged:

- `render.yaml` remains `cors_app:APP`;
- `france_app.py` is removed;
- `cors_app.py` installs `install_france_decp_runtime(...)` additively alongside the existing global runtime installers;
- activation policy still comes from the canonical preload/source-registry gate.

The runtime remains inert unless:

1. the source passes `source_registry.production_gate_reasons`; and
2. `FR_DECP` is explicitly requested in `OBRASIGNAL_GLOBAL_SOURCES`.

This preserves one modular-monolith runtime composition root and avoids a France-specific runtime fork.

## Registry decision

`FR_DECP` is registered as:

- official;
- `ready`, not `active`;
- public Explore API;
- legal reuse `GREEN` based on the official Open Licence v2.0 metadata;
- machine access `VERIFIED` based on official public API/source validation;
- expected refresh 1440 minutes;
- signal type `CONTRACT`;
- capabilities: incremental sync, contracts, historical data, suppliers;
- no canonical Wave-1 assignment.

`ready` means code/evidence is prepared behind the production gate. It does not mean deployed or actively ingesting.

## Test plan and evidence

Mock/unit coverage includes:

- canonical `CONTRACT` type;
- construction CPV filter;
- amount/currency;
- stable identity;
- re-observed same-ID update safety;
- publisher-derived publication cursor;
- empty result semantics;
- malformed schema;
- missing identity/update date;
- bounded timeout retries;
- rate-limit recovery;
- pagination-cap failure;
- unsafe URL rejection;
- registry gate;
- runtime callback boundary;
- canonical Signal idempotent update.

The consolidation adds `test_france_integration_wiring.py` to lock the architecture decision: Render must continue to point at `cors_app:APP`, `france_app.py` must not exist, the canonical WSGI root must install the France runtime, and `FR_DECP` must remain `ready` with no Wave-1 promotion.

The dedicated GitHub Actions live smoke (`.github/workflows/france_decp_live.yml`) performs a bounded, credential-free request against the official DECP API and validates that live construction records normalize to canonical `CONTRACT` signals. The workflow now checks out and asserts the exact PR HEAD before source validation. The PR check is the authority for `LIVE_VALIDATED`; production deployment is never inferred from this smoke.

## Known limitations

- BOAMP legacy ingestion remains a separate pre-existing connector and was not redesigned here.
- DECP is post-award/contract data; it is not an early-signal or forecast source.
- Complete incremental capture of amendments to older DECP 2022 contracts is not claimed because the current modification-publication field is text.
- Procurement-plan / capital-pipeline coverage remains a separate future source question and is not invented from DECP.
- `FR_DECP` is not automatically requested in production environment configuration by this branch.
- Source-side schema changes remain a maintenance risk; live CI smoke is intentionally retained as an early warning.

## 100-hour test

**Pass.** The incremental build is substantially below a 100-hour bespoke integration in architecture terms because it reuses the existing incremental runtime, canonical Signal store, source health, cursor transaction and production gate. It adds contract intelligence to an already-core commercial market without creating a parallel France-specific domain model.

## Integration reconciliation / zero-silent-conflict record

- PR #171 source implementation HEAD: `e8209221d21d30f009021f3088df8c0a172a78d7`.
- Reconciled against current main `fce51d5b5524e09691f9187f7619ea0166217487`.
- Source adapter, runtime helper, tests, registry metadata, rights/access evidence and live-source workflow are preserved.
- The old `france_app.py` / Render-start-command composition choice is superseded by canonical `cors_app.py` integration.
- No Master Queue mutation, no deployment mutation, no environment activation and no automatic merge are part of this reconciliation.

## Final classification

**France — `BUILD` / dedicated official lifecycle enrichment prepared for integration.**

- Tender discovery: existing BOAMP + complementary TED/eForms.
- Contract intelligence: DECP `CONTRACT` connector implemented and runtime-composable behind the canonical gate.
- Shared vs bespoke decision: shared canonical runtime/storage; only the source adapter is France-specific.
- Integration state: implementation reconciled to current main; exact-head CI/live gates must be green on the final integration HEAD before `COMBINATION_VALIDATED` / `LIVE_VALIDATED` are claimed.
- Production status: **NOT CLAIMED**.
