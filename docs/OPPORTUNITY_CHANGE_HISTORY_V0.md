# ObraSignal Opportunity Change History / Material Diff v0

**Capability state:** RESEARCH  
**Owner domain:** SIGNAL  
**Contract:** `opportunity_change_history.v0`  
**Feature flag:** `opportunity_change_history_v0` (future rollout metadata; not activation)

## PURPOSE

Answer one product question reliably:

> What changed in this opportunity since the previous canonical state we knew?

The capability observes normalized Signal records and preserves a compact, chronological explanation of meaningful state transitions. `signal_records` remains the source of truth for current canonical state; history is an audit/read layer, not a competing opportunity store.

## NON-GOALS

V0 is not an alerts system, Evidence Graph, generic activity feed, document version-control system, PDF redline engine, legal interpretation engine, decision invalidator or notification inbox. It does not parse new lot/document/requirement structures and does not change connector transport behavior.

## REPOSITORY FIT

The accepted architecture remains:

`SOURCE -> CONNECTOR -> NORMALIZATION -> CANONICAL MODEL -> PRODUCT ENGINE`

Change History sits after normalization and observes the same staged canonical records used by Signal persistence.

`source_runtime.commit_staged_source_syncs()` contains a dormant integration seam so a separately authorized future maturity decision can execute history before the current Signal upsert and inside the same transaction. With the canonical capability state at `RESEARCH`, the seam is inactive and normal Signal/metadata/lifecycle/cursor persistence proceeds without touching Change History tables.

The canonical Master Execution Queue is not modified by this capability. The branch was originally cut from `main` at `9b100d4c860a0e9c5d9eb096db1fb62c9ce62af1` while Q080 Evidence Graph was ACTIVE. Capability-registry lifecycle is independent of queue state and passing tests do not promote maturity.

## SNAPSHOT MODEL

`opportunity_snapshots` stores monitored canonical fields plus audit metadata:

- source / signal type / external ID;
- native source version when explicitly available;
- observation and source-update timestamps;
- compact canonical JSON;
- deterministic content fingerprint;
- normalizer version;
- schema version.

The first observed state is a baseline, not a fabricated change. When the module is introduced for an opportunity already present in `signal_records`, it can bootstrap the existing normalized current record as the previous baseline before evaluating the incoming observation.

Snapshots are chronological. A reversal `A -> B -> A` creates three snapshots because returning to a previously seen state is still a real later observation. Idempotency is based on equality with the latest snapshot, not on global fingerprint uniqueness.

## CHANGE MODEL

`opportunity_change_sets` groups one source observation that changed one or more monitored fields. It records canonical identity, previous/current snapshot IDs, native revision when available, source/evidence reference, detected/source-update times, aggregate materiality, changed fields and versioned diff metadata.

`opportunity_changes` records each field/item transition with:

- field;
- change type (`ADDED`, `CHANGED`, `ITEM_ADDED`, `ITEM_REMOVED`, or conservative `UNKNOWN_CHANGE` in the pure engine);
- old/new normalized values;
- materiality;
- deterministic detail when available, currently `EXTENDED` / `SHORTENED` for deadline changes.

Change rows are append-only in v0.

## FIELD REGISTRY

V0 diffs only centrally registered product fields:

- `deadline`;
- `value`;
- `currency`;
- `source_status`;
- `lifecycle_status`;
- `source_version` (publisher-native amendment/revision identity);
- `title`;
- `description`;
- `buyer`;
- `place`;
- structured `lots`;
- structured `documents`;
- structured `requirements`.

Technical timestamps, retrieval hashes and connector-private fields are absent from the registry and cannot create user-facing noise. Publisher-native revision identity is deliberately not treated as a technical timestamp: a real amendment/revision transition is itself material provenance and must not disappear merely because other normalized fields happen to be unchanged.

## NORMALIZATION

Comparison uses canonical monitored values, never raw HTML/XML.

Rules are intentionally narrow:

- collapse whitespace before any large-text digest is calculated;
- ignore capitalization only for policy-approved fields and do so before large-text digesting;
- normalize safe/unambiguous dates deterministically;
- normalize decimal values without guessing locale separators;
- keep currency semantically independent from amount;
- treat registered collections as order-independent;
- use stable item identity only when safe, otherwise fall back to field-level `CHANGED`;
- replace oversized monitored text with digest + bounded excerpt;
- enforce a total monitored-snapshot byte ceiling.

## MATERIALITY

V0 uses explicit registry rules. It does not use an LLM or opaque score. Current monitored business fields, including publisher-native source revision/amendment identity, are `MATERIAL`; unresolved missing-state ambiguity in the pure engine is `UNKNOWN`.

## NULL / MISSING SEMANTICS

An absent key in an incoming normalized record means **not observed in this payload**, not automatically **removed**. If a previous value exists, it is carried forward.

An explicit null/empty value is observable and can represent a confirmed removal where connector semantics make that assertion reliable.

## COLLECTION SEMANTICS

`lots`, `documents`, and `requirements` are order-independent. Pure reorder does not create a change.

Stable identity is resolved only from configured safe identity keys. Add/remove becomes `ITEM_ADDED` / `ITEM_REMOVED`. If identity is ambiguous or duplicated, the engine falls back to one field-level `CHANGED` result rather than inventing identity.

## IDEMPOTENCY

`A -> B -> B` produces one change set for `A -> B`.

`A -> B -> A` produces two real change sets.

`A -> B -> A -> B` preserves all three real transitions. Duplicate delivery is suppressed by comparing the incoming fingerprint with the latest persisted snapshot before creating anything. Because `source_version` is monitored when present, `revision r1 -> r2` is a real transition even if all other monitored business values are unchanged.

## NATIVE AMENDMENTS / SOURCE VERSION

Native revision identity wins when explicitly normalized. Supported aliases are `amendment_number`, `revision_id`, `amendment_id`, `corrigendum_id`, `native_revision`, and `release_id`; they are projected into `source_version` for history only.

CanadaBuys already normalizes `amendment_number` and `amendment_date`; the dormant source transaction seam can alias those values into the generic history contract without altering current Signal persistence or fabricating a source version when the capability is explicitly promoted in future.

A publisher-native revision-only change therefore creates a material change set with `changed_fields = ["source_version"]` when the pure persistence path is invoked. The same alias logic is applied when reconstructing a pre-module baseline from `signal_records.normalized_json`, so the previous amendment number is not lost during a controlled rollout.

## PERSISTENCE AND TRANSACTION SAFETY

No separate database is introduced. Tables are created idempotently in the existing SQLite database only when the Change History persistence contract is deliberately invoked.

Future source-side sequence after an explicit maturity/activation decision:

1. load/bootstrap previous monitored state;
2. normalize incoming monitored state;
3. detect and persist history;
4. persist/update current Signal;
5. persist source metadata;
6. persist lifecycle;
7. advance source cursor;
8. commit once.

Any deliberately enabled-history exception rolls the complete source-side transaction back. Reprocessing after a rolled-back attempt is safe.

## RUNTIME DISABLE BOUNDARY

The capability registry is the v0 runtime disable boundary. Only `PILOT` and `ENABLED` execute history persistence. `RESEARCH`, `EXPERIMENT`, `DISABLED` and other non-promoted states skip Change History while Signal, metadata, lifecycle and cursor persistence continue normally.

The current branch deliberately registers `OPPORTUNITY_CHANGE_HISTORY` as `RESEARCH`, so normal repository runtime does **not** create or update Change History state. Tests of the future active path use an explicit test-only `PILOT` override; they do not change canonical maturity.

The declared `feature_flag = opportunity_change_history_v0` is metadata for future scoped rollout. This branch does not invent a global customer/environment feature-flag service that does not already exist in the repository.

## VERSIONING

Persisted history carries:

- `schema_version = 1`;
- `normalizer_version = canonical-change-normalizer-v0`;
- `diff_policy_version = opportunity-material-diff-v0`.

## DEADLINE DIRECTION SAFETY

When both normalized deadline values are directly comparable, changes are annotated as `EXTENDED` or `SHORTENED`. Mixed offset-aware/offset-naive representations remain a material deadline change but do **not** assert direction; direction becomes `null` rather than allowing a Python timezone-comparison `TypeError` to abort source ingestion.

## EVENT CONTRACT

The module exposes a pure compact projection for future generic event infrastructure:

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

V0 does **not** enqueue or deliver this event. Existing `notification_events.py` is account-scoped alert delivery and is deliberately not reused as a generic canonical event bus.

## READ MODEL / API BOUNDARY

`get_change_history()` returns newest-first change sets with structured changes and supports `material_only=True`.

No HTTP/UI surface is added in v0. Existing HTTP opportunity detail uses legacy `tenders.id`, while durable Signal/history identity is `(source, signal_type, external_id)`. A thin adapter should be added only after the canonical API identity boundary is agreed.

## SECURITY

Source content is untrusted.

- SQL writes/reads use bound parameters;
- history never evaluates source strings;
- JSON uses the standard encoder;
- giant text and total snapshot size are bounded;
- whitespace/case normalization happens before large-text hashing, preventing false material changes caused only by formatting noise;
- raw publisher HTML/XML is not stored here;
- connector-private keys are not monitored;
- no new private/account data is introduced.

A future HTML UI must escape values at render time; persistence deliberately does not destructively HTML-escape canonical text.

## TESTING

Dedicated tests cover identical-state idempotency, deadline extension/shortening/reversal, mixed aware/naive deadline safety, repeated real transitions, date equivalence, value/currency/status changes, whitespace/case noise suppression including oversized text, real title changes, collection reorder, document/lot add/remove, multi-field grouping, missing vs explicit null, duplicate delivery, bootstrap from existing Signal state, native amendment provenance, revision-only publisher amendments, reconstructed amendment baselines, deterministic fingerprints, material-only reads, event projection, hostile source strings, oversized-state fail-closed behavior, transaction rollback, explicit future-active-path behavior and non-promoted runtime inactivity.

Repository quality gates additionally compile root Python modules and run the full Python suite plus Expo/mobile checks. CI status is evidence attached to the exact PR/head under test; documentation does not convert a passing branch test into a production or maturity claim.

## KNOWN LIMITATIONS

- Only fields already normalized by a connector can be compared.
- Connectors vary in structured lots/documents/requirements coverage.
- A native revision proves that the publisher revised the opportunity; it does not by itself explain unnormalized document-body semantics.
- No semantic LLM/PDF redline.
- No cross-source authority reconciliation.
- No user seen/unseen state.
- No retention/compaction policy until storage growth is measured.
- Event delivery is intentionally absent.
- HTTP/UI exposure is intentionally deferred pending canonical identity/API integration.
- Pre-module history cannot be invented beyond a reconstructible current Signal baseline.
- Runtime execution remains intentionally inactive while the capability is RESEARCH.

## FUTURE INTEGRATIONS

Alerts/Watchlist may consume `opportunity.changed`; Compare may show `updated since last review`; Readiness may mark prior analysis stale; Evidence Graph may enrich evidence refs; a future canonical API adapter may expose material/all history. None is a dependency or production claim of this module.

## ROLLBACK

Because the capability is additive, rollback consists of removing the dormant `source_runtime` history import/call and capability-registry entry. Existing Signal, metadata, lifecycle, legacy tenders, decisions and source cursors retain their prior contracts. Historical tables created by explicit tests or a future controlled activation may remain inert for audit or be removed later through an explicit retention/migration decision.
