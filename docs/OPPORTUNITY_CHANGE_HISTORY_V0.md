# ObraSignal Opportunity Change History / Material Diff v0

**Capability state:** PILOT  
**Owner domain:** SIGNAL  
**Contract:** `opportunity_change_history.v0`  
**Feature flag:** `opportunity_change_history_v0`

## PURPOSE

Answer one product question reliably:

> What changed in this opportunity since the previous canonical state we knew?

The capability observes normalized Signal records and preserves a compact, chronological explanation of meaningful state transitions. Current `signal_records` remains the source of truth for current canonical state; history is an audit/read layer, not a competing opportunity store.

## NON-GOALS

V0 is not an alerts system, Evidence Graph, generic activity feed, document version-control system, PDF redline engine, legal interpretation engine, decision invalidator or notification inbox. It does not parse new lot/document/requirement structures and does not change connector transport behavior.

## REPOSITORY FIT

The existing architecture defines `SOURCE -> CONNECTOR -> NORMALIZATION -> CANONICAL MODEL -> PRODUCT ENGINE`. Change History sits after normalization and observes the same staged canonical records used by Signal persistence.

`source_runtime.commit_staged_source_syncs()` is the existing source-side transaction boundary. History detection/persistence executes before the current Signal upsert, inside that same transaction, so the previous state is still available and history/current/cursor movement cannot partially commit.

The canonical Master Execution Queue is not modified. `Q060_CHILE_MERCADOPUBLICO` remains the active queue item. Capability-registry lifecycle is independent of queue state.

## SNAPSHOT MODEL

`opportunity_snapshots` stores only monitored canonical fields plus audit metadata:

- source / signal type / external ID;
- native source version when explicitly available;
- observation and source-update timestamps;
- compact canonical JSON;
- deterministic content fingerprint;
- normalizer version;
- schema version.

The first observed state is a baseline, not a fabricated change. When the module is introduced for an opportunity already present in `signal_records`, it can bootstrap the existing normalized current record as the previous baseline before evaluating the incoming observation.

Snapshots are chronological. A reversal `A -> B -> A` creates three snapshots because returning to a previously seen state is still a real later observation. Idempotency is instead based on equality with the *latest* snapshot.

## CHANGE MODEL

`opportunity_change_sets` groups one source observation that changed one or more monitored fields. It records:

- deterministic internal change-set ID;
- opportunity canonical identity;
- previous/current snapshot IDs;
- native revision when available;
- source/evidence reference when available;
- detected/source-updated times;
- aggregate materiality;
- changed field list;
- diff-policy/schema versions.

`opportunity_changes` records each field/item transition with:

- field;
- change type (`ADDED`, `CHANGED`, `ITEM_ADDED`, `ITEM_REMOVED`, or conservative `UNKNOWN_CHANGE` in the pure engine);
- old/new normalized values;
- materiality;
- deterministic detail when available, currently `EXTENDED` / `SHORTENED` for deadline changes.

Change rows are append-only in v0. Correction/supersession semantics are reserved for a later contract rather than silently editing historical events.

## FIELD REGISTRY

V0 diffs only centrally registered product fields:

- `deadline`;
- `value`;
- `currency`;
- `source_status`;
- `lifecycle_status`;
- `title`;
- `description`;
- `buyer`;
- `place`;
- structured `lots`;
- structured `documents`;
- structured `requirements`.

A connector must already normalize a structured collection for collection-aware diffing. V0 does not invent a parser from raw PDF/HTML/attachment text merely to populate these fields.

## NORMALIZATION

Comparison uses canonical monitored values, never raw HTML/XML.

Rules are intentionally narrow:

- whitespace is collapsed in text;
- capitalization is ignored only for fields whose registry policy declares it safe (`title`, `buyer`, status, currency, place);
- ISO and a small set of unambiguous date formats normalize deterministically;
- numeric canonical values use decimal normalization without guessing locale separators;
- currency remains a separate monitored semantic, therefore `1000000 EUR != 1000000 GBP`;
- order-independent collections are sorted by deterministic canonical JSON;
- retrieval timestamp and connector-private fields are excluded from fingerprints.

Large strings are represented in monitored state by a SHA-256 digest plus bounded excerpt instead of copying giant prose into every historical row. Whole-snapshot persistence also has a byte ceiling and fails closed if exceeded.

## MATERIALITY

V0 uses explicit registry rules. It does not use an LLM or opaque score to decide materiality.

All currently monitored v0 business fields are `MATERIAL`. Unknown/removal ambiguity exposed by direct pure-engine calls is `UNKNOWN`. Technical fields are not registered and therefore do not create user-facing changes.

This conservative starting point is deliberate: it is easier to add an explicit `NON_MATERIAL` field policy later than to explain false material claims generated by heuristic inference.

## NULL / MISSING SEMANTICS

An absent key in an incoming normalized record means **not observed in this payload**, not automatically **removed**. If a previous value exists, it is carried forward.

An explicit null/empty value is observable and can represent a confirmed removal where connector semantics make that assertion reliable. This prevents temporary sparse source responses from fabricating removals.

## COLLECTION SEMANTICS

`lots`, `documents`, and `requirements` are order-independent in v0. A pure reorder does not create a change.

Stable item identity is resolved only from an explicit safe identity key configured for the field. Add/remove becomes `ITEM_ADDED` / `ITEM_REMOVED`. If identity is ambiguous or duplicated, the engine falls back to one field-level `CHANGED` result rather than inventing item identity.

## IDEMPOTENCY

Processing:

`A -> B -> B`

produces one change set for `A -> B`.

Processing:

`A -> B -> A`

produces two real change sets.

A later real repetition `A -> B -> A -> B` remains three transitions. Change-set identity includes chronological snapshot IDs, while redelivery idempotency is enforced by comparing the incoming fingerprint with the latest persisted snapshot before creating anything.

## NATIVE AMENDMENTS / SOURCE VERSION

Native revision identity wins when explicitly normalized. Supported generic names include `source_version`, `revision_id`, `amendment_id`, `corrigendum_id`, `native_revision`, and `release_id`.

The existing CanadaBuys connector already normalizes `amendment_number` and `amendment_date`; the source transaction boundary aliases those values into the generic history contract without changing Signal current-state persistence. This preserves publisher identity rather than treating `source_reference` as an invented revision.

No version is fabricated when a source exposes no native revision. The observation/snapshot fingerprint is then internal ObraSignal identity only.

## PERSISTENCE AND TRANSACTION SAFETY

No separate database is introduced. Tables are created idempotently in the existing SQLite database.

For staged source ingestion the sequence is:

1. load/bootstrap previous canonical monitored state;
2. normalize incoming monitored state;
3. detect and persist history;
4. persist/update current Signal;
5. persist source metadata;
6. persist lifecycle;
7. advance source cursor;
8. commit once.

Any exception rolls the complete source-side transaction back. Reprocessing after a rolled-back attempt is therefore safe.

## CURRENT STATE

`signal_records` remains the current canonical Signal source of truth. History does not require connectors to read/write its private tables and does not replace `tenders` compatibility projection or lifecycle tables.

## VERSIONING

Persisted history carries:

- `schema_version = 1`;
- `normalizer_version = canonical-change-normalizer-v0`;
- `diff_policy_version = opportunity-material-diff-v0`.

These identifiers are deliberately separate so future replay/audit can distinguish schema evolution from normalization or materiality policy changes.

## EVENT CONTRACT

The module exposes a pure compact event projection for future generic event infrastructure:

```json
{
  "event_type": "opportunity.changed",
  "event_version": 1,
  "opportunity_id": {
    "source": "...",
    "signal_type": "TENDER",
    "external_id": "..."
  },
  "change_set_id": "...",
  "changed_fields": ["deadline"],
  "materiality": "MATERIAL"
}
```

V0 does **not** deliver or enqueue this event. The current `notification_events.py` table is account-scoped alert delivery for `new_high_match`; coupling global canonical history to it would mix two responsibilities.

## READ MODEL

`get_change_history()` returns newest-first change sets with structured changes and supports `material_only=True`. This is suitable for a future UX such as:

- Deadline changed — 10 Sep -> 17 Sep;
- New document added — Technical specification v2;
- Published value changed — 1.8M EUR -> 2.0M EUR.

No HTTP/UI surface is added in v0. Existing HTTP opportunity IDs are legacy `tenders.id`, while the durable Signal/history identity is `(source, signal_type, external_id)`. Exposing a route before agreeing the canonical API identity would add a legacy coupling to a new core capability. The service read model is complete and can be surfaced through a thin adapter once that identity decision is made.

## SECURITY

Source content is untrusted.

- SQL writes/reads use bound parameters;
- history never evaluates source strings;
- JSON is serialized by the standard encoder;
- giant text is bounded/digested;
- total monitored snapshot size is capped;
- raw publisher HTML/XML is not stored here;
- connector-private keys are not part of monitored state;
- no new private/account data is introduced.

A future HTML UI must still escape values at render time; persistence deliberately does not destructively HTML-escape canonical text.

## TESTS

Dedicated tests cover:

- identical-state idempotency;
- deadline change, extension, shortening, and reversal;
- date normalization;
- value and currency changes;
- status changes;
- whitespace/capitalization false-change suppression;
- real title changes;
- order-only collection changes;
- document/lot add/remove;
- multi-field change-set grouping;
- missing vs explicit-null semantics;
- repeated delivery idempotency;
- repeated real transition chronology;
- bootstrap from pre-existing `signal_records`;
- native amendment/source reference/version retention;
- deterministic fingerprints;
- material-only read model;
- event-contract projection;
- hostile source strings;
- oversized snapshot fail-closed behavior;
- source-runtime transaction rollback after history failure.

Repository CI additionally compiles root Python modules and runs the full Python tests plus Expo/mobile checks.

## KNOWN LIMITATIONS

- Only fields already normalized by a connector can be compared.
- Current connectors do not all expose structured lots/documents/requirements.
- No semantic LLM diff of prose/PDF contents.
- No cross-source authority reconciliation.
- No user seen/unseen state.
- No retention/compaction policy is invented; storage growth should be measured first.
- Event delivery is intentionally absent.
- HTTP/UI exposure is intentionally deferred pending canonical identity/API integration.
- Changes observed before the first reconstructible current Signal baseline cannot be retroactively invented.

## FUTURE INTEGRATIONS

Safe follow-ons, after their own contracts are ready:

- Alerts/Watchlist may consume `opportunity.changed` and decide whether a user needs attention;
- Compare may show `updated since last review`;
- Readiness may mark prior analysis stale after relevant material fields change;
- Evidence Graph may attach richer evidence refs;
- Requirements may feed structured requirement versions;
- decision/outcome layers may explicitly model stale decisions;
- a canonical API adapter may expose material/all history without leaking internal table structure.

None of these are implemented or claimed by this module.

## ROLLBACK

Because the capability is additive, rollback consists of removing its source-runtime call/import and registry entry. Existing `signal_records`, metadata, lifecycle, legacy tenders, decisions and source cursors retain their prior contracts. Historical tables can remain inert for audit or be removed later through an explicit migration after retention requirements are decided.
