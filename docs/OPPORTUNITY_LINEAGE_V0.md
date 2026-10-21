# ObraSignal Opportunity Lineage / Notice Family v0

## Purpose

Opportunity Lineage answers one narrow question: **which canonical procurement events are defensibly part of the same procurement lifecycle?** It links plans, market dialogue, tenders, amendments/corrigenda, awards and contracts only when source-native or deterministic identity evidence supports the relationship.

This capability is additive. It does not replace `opportunity_lifecycle.py` (current commercial state), Change History (versions/changes within an opportunity), Evidence Graph (proof/provenance), buyer resolution, or the canonical Signal store.

## Non-goals

- Generic entity resolution or a universal knowledge graph.
- Fuzzy auto-linking based on title, value, location, buyer, or temporal proximity.
- ML/embedding/LLM matching.
- Destructive family merge/split operations.
- Reinterpreting source-specific eForms/OCDS payloads inside the lineage core.
- Claiming Award/Contract ingestion coverage where a connector does not already emit canonical signals.
- Future Demand, expiry prediction, procurement prediction, or workflow automation.

## Repository state used by v0

- `signal_store.py` is the canonical durable envelope and already permits `PROCUREMENT_PLAN`, `MARKET_DIALOGUE`, `TENDER`, `AWARD`, and `CONTRACT`.
- There are no separate canonical Award/Contract model modules on `main`; v0 therefore works on canonical Signal records rather than inventing competing models.
- `ocds_adapter.py` already preserves `ocid`, `source_reference`, source phase/tags, and normalized provenance.
- `opportunity_lifecycle.py` owns actionable/current lifecycle state and remains unchanged.
- `lot_matcher.py` exposes `lot_id` / `technical_lot_id`; lineage respects these identifiers when present.
- The modular ADR requires a replaceable capability behind explicit contracts and canonical data boundaries.
- The canonical Master Execution Queue remains unchanged; its active item is outside this parallel branch.

## Node types

The core accepts only canonical procurement lifecycle nodes:

- `PROCUREMENT_PLAN`
- `MARKET_DIALOGUE`
- `TENDER`
- `AMENDMENT`
- `CORRIGENDUM`
- `AWARD`
- `CONTRACT`

`AMENDMENT` and `CORRIGENDUM` can be represented with `lineage_node_type` when the underlying canonical Signal still uses a compatible existing signal type. This avoids widening the Signal Contract in a parallel module.

## Relationship types

V0 intentionally keeps a small vocabulary:

- `PRECEDES`
- `DERIVED_FROM`
- `AMENDS`
- `CORRECTS`
- `SUPERSEDES`
- `RESULTED_IN`
- `CONTRACTED_AS`
- `RELATED_TO`

Award and Contract are not treated as equivalent. A tender may result in multiple awards, and an award may contract into multiple contracts.

## Explicit vs deterministic vs inferred

### EXPLICIT

`lineage_relations` / `related_notices` supplied by a normalized connector are authoritative source-native evidence. The relation preserves native type, target identifiers and source reference. Explicit relations are `HIGH` confidence.

An explicit relation with a target not present in the supplied canonical record set remains `UNRESOLVED`; the engine does not manufacture the target.

### DETERMINISTIC

Confirmed only from strong canonical identity:

1. the same non-empty OCDS `ocid`; or
2. the same non-empty official procurement/procedure reference **within the same jurisdiction**.

Same-stage records are deliberately not deterministically linked: tender v1 → tender v2 is Change History territory unless the publisher gives an explicit cross-notice lineage relation.

### INFERRED / candidates

Weak evidence never becomes a confirmed edge in v0. Candidate generation is bounded by buyer + jurisdiction and requires at least two supporting signals. Typical candidate reasons include same buyer identifier, same exact normalized title and same source reference. Candidates remain `UNRESOLVED`.

## Identity rules

Strong identity is not title, value, place, buyer, or timing. `ocid` and source/publisher procurement identifiers are reused rather than replaced with a new invented global procurement ID. `canonical_process_id` stores the strongest available known process identity (`ocid` first, official procurement reference second) and may remain null.

Node identity is stable and local: `source:external_id`.

## Source-native relations

Connectors may normalize source relations into a small structure such as:

```python
{
  "lineage_relations": [
    {
      "target_source": "SOURCE_A",
      "target_external_id": "123",
      "relationship_type": "SUPERSEDES",
      "native_relation_type": "previousNotice",
      "source_ref": "official-reference-or-url"
    }
  ]
}
```

The core performs no source-specific XML/JSON parsing. Native identifiers and native relation labels are preserved for audit.

## OCDS / eForms handling

OCDS `ocid` continuity is a strong lineage key between **different lifecycle stages**. It is not treated as evidence that two same-stage releases are separate lifecycle nodes; those may instead be version/change observations.

eForms relationships should be normalized by the source adapter when/where the adapter already understands the publisher semantics. V0 does not reinterpret eForms XML from the core.

## Cross-source safety

Cross-source explicit references are accepted and preserved. Cross-source deterministic linking requires the same strong identity (for example, the same OCID or official procurement reference within jurisdiction). Same buyer/title without strong identity stays unresolved/candidate.

## Lots and 1:N semantics

When both nodes carry lot identifiers, different lot IDs cannot be linked. A procedure-level tender without a lot ID may link to multiple lot-specific awards. Each lot-specific award can then link only to contracts for the same lot when lot identifiers exist.

The model permits:

- one tender → many awards;
- one award → many contracts;
- framework-like 1:N structures without pretending to solve full framework/call-off semantics in v0.

## Ambiguity and false-merge controls

The engine deliberately refuses to confirm lineage for:

- same title + different buyer;
- same buyer + different official procurement IDs;
- same value + same place;
- same buyer + adjacent dates;
- re-tenders that only resemble the prior tender;
- cross-source records without strong identity or explicit cross-reference.

Ambiguous evidence remains visible as an unresolved candidate.

## Idempotency and replayability

`detect_lineage_relations(records)` is pure and deterministic for the same canonical records and `LINEAGE_RULE_VERSION`. It snapshots inputs before and after detection and raises if the detector mutates the supplied source records.

Persisted edge identity is a hash of from/to/type/basis/provenance/rule/lot semantics. Reprocessing the same relation is `INSERT OR IGNORE`, so duplicate edges are suppressed.

## Persistence

V0 uses additive SQLite tables, consistent with the current repository:

- `procurement_lineage_nodes`
- `procurement_lineage_edges`

No graph database is introduced. Indexes cover source identity, canonical process identity, and edge adjacency. Schema creation is idempotent and non-destructive.

The branch intentionally does not auto-wire persistence into every ingestion path. That would silently change production behavior from a parallel module. Integration should call lineage persistence after canonical Signal persistence, inside the same controlled transaction when promoted.

## Cycles

Directional lifecycle semantics (`SUPERSEDES`, `AMENDS`, `CORRECTS`, `PRECEDES`, `RESULTED_IN`, etc.) are protected against cycles. Edges are evaluated deterministically with explicit relations first. A cycle-producing edge is rejected and returned with reason `cycle prevented` rather than silently accepted.

`RELATED_TO` is non-DAG and is not subject to directional cycle rejection.

## Read model

`lineage_view(conn, entity_id=...)` returns:

- canonical process identity when known;
- jurisdiction;
- family nodes;
- relationships including basis/confidence/provenance;
- chronological timeline;
- latest **known dated stage**;
- coverage note for nodes without dates.

Date ordering uses `effective_at`, then `occurred_at`, `published_at`, `source_updated_at`, `publication_date`, then `target_date`. Missing dates remain in the family and sort after dated nodes; no precise date/order is invented.

## API / UI

No production API route or UI panel is wired in v0. The current public surfaces are legacy-tender-centric, while the lineage contract spans canonical non-tender Signals. Adding a route now would create a misleading partial integration. The read model is intentionally ready for a future `GET /api/v1/opportunities/{id}/lineage` or procurement-process route after canonical Signal detail routing is promoted.

A future UI should label official/deterministic versus inferred relations distinctly and show gaps rather than drawing a falsely continuous history.

## Security

- All SQL values are parameterized.
- Lineage identifiers and relation reasons have bounded lengths.
- Unknown node/relation/basis/confidence values fail closed.
- Persisted fields remain plain data; UI consumers must escape output as usual.
- No raw publisher payloads are persisted by this module.
- No tenant-private annotations are created; public procurement lineage is shared canonical data.

## Performance

There is no global all-to-all comparison. Deterministic detection blocks on OCID or jurisdiction+official procurement reference. Candidate generation blocks on jurisdiction+buyer identity/label. These bounded buckets avoid global O(N²) matching while retaining conservative matching behavior.

## Tests

`test_procurement_lineage.py` covers:

- explicit plan→tender, tender→award, award→contract;
- amendment/corrigendum targets;
- OCDS OCID continuity;
- same-stage/change-history boundary;
- false positives for title/buyer/value/location/time;
- explicit and weak cross-source cases;
- official procurement reference continuity;
- multiple awards/contracts;
- lot isolation;
- cancellation and re-tender safety;
- missing-date timeline;
- cycle prevention;
- edge idempotency;
- deterministic output and no input mutation;
- property-style unrelated-record stability;
- explicit-over-weak precedence;
- malformed/oversized input and SQL-like identifiers;
- idempotent schema creation.

## Known limitations

- Existing adapters do not uniformly expose source-native notice relationships yet.
- Existing OCDS normalization is primarily tender-oriented even though the Signal Contract permits Award/Contract records; v0 does not falsely claim those connectors emit every lifecycle stage.
- No destructive merge/split reconciliation workflow exists.
- Candidate decisions are not persisted; they are pure detector output in v0.
- No broad historical backfill is started automatically.
- No production API/UI wiring is claimed.

## Future integrations

Potential consumers, not implemented here: Buyer Intelligence, Procurement Plan Intelligence, Expiring Contract Signals, Future Demand, Change History, Evidence Graph, Opportunity Brief and COMMAND.

A bounded `backfill_lineage` dry-run command may be added only when a canonical integration path is selected; inferred/cross-source backfills should be inspected before persistence.

## Rollback

Rollback is code/schema-safe: stop calling the capability and remove the two additive lineage tables if desired. The module never mutates canonical Signal rows, Opportunity lifecycle state, Award data, Contract data, or the Master Execution Queue.
