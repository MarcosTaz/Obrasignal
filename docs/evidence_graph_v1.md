# ObraSignal Proof / Evidence Graph v1

## Purpose

Evidence Graph v1 provides a small, deterministic, provenance-first domain model for answering three product questions without relying on an opaque score or an LLM as source of truth:

- **WHY?** — reconstruct the material lineage behind a claim or recommendation input.
- **SHOW ME.** — return structured supporting evidence and source provenance suitable for a presentation layer.
- **WHAT IF?** — retain dependency lineage and calculation versions so later sensitivity tooling can replay affected claims.

This is an internal capability contract. It does **not** promote `Q080_EVIDENCE_GRAPH_V1`, alter the canonical Master Execution Queue, expose a public API, or claim production integration.

## Architecture decision

V1 is an in-process directed graph implemented with immutable snapshot records plus dictionaries/sets for graph indexing. It deliberately adds no Neo4j, graph service, external database, or new infrastructure.

The graph is currently **in-memory only**. `EvidenceGraph.export()` produces a deterministic detached snapshot structure but does not itself persist it. A future persistence adapter may use existing ObraSignal storage conventions after the storage boundary is explicitly designed.

`DECISION` is not a claim type in v1. Decisions consume evidence-backed claims; this prevents an operational choice from being confused with the epistemic categories used to justify it. The existing decision log remains the existing decision log rather than being duplicated.

## Domain model

### Nodes

| Node | Meaning |
| --- | --- |
| `EVIDENCE` | An externally or internally attributable observation carrying provenance. |
| `FACT` | A material claim directly supportable by evidence. |
| `ESTIMATE` | A calculated or approximate value derived from known inputs and/or assumptions. |
| `INFERENCE` | A conclusion derived from facts, estimates, or other supported lineage. |
| `ASSUMPTION` | An explicitly unconfirmed input used in reasoning. |

Missing data remains missing. A claim whose value is `None` is `UNKNOWN`; it is not silently converted into `0`, `False`, or `LOW`.

### Edges

| Edge | Semantics |
| --- | --- |
| `SUPPORTS` | Evidence materially supports a claim. |
| `DERIVED_FROM` | A derived claim depends on another supported node. |
| `DEPENDS_ON` | Generic dependency when a stronger semantic edge is inappropriate. |
| `USES_ASSUMPTION` | A calculation/inference explicitly relies on an assumption. |
| `CONTRADICTS` | Two claims/evidence paths materially disagree. It does not silently choose a winner. |
| `SUPERSEDES` | A newer claim replaces an older claim while preserving history. Direction is `new -> old`. |

Derivation dependencies are cycle-protected. `SUPERSEDES` is also cycle-protected but is intentionally excluded from ancestry returned for WHY/WHAT-IF dependency traversal: a replacement is historical version metadata, not an input to the superseded claim.

## Claim contract

A claim carries, as applicable:

- stable content-derived `claim_id`;
- `claim_type`;
- `subject`;
- `predicate`;
- `value`;
- `unit`;
- `valid_at`;
- `method`;
- `calculation_version`;
- explanation metadata.

Graph snapshots also carry `model_version` and `policy_version`.

IDs are derived from canonicalized claim/evidence content plus tenant identity. The same inputs and versions therefore produce the same IDs and export ordering.

## Audit immutability

Material node content is snapshotted on insertion. Nested mappings are read-only snapshots and nested sequences are immutable tuples/frozensets inside the graph. Mutating caller-owned dictionaries/lists after insertion cannot rewrite an existing node without changing its identity.

Presentation/export views are detached copies. Mutating a returned `explain()` or `export()` structure does not mutate the graph's audit state.

This provides in-process immutability only. V1 still makes no claim of persisted WORM/audit-log durability.

## Provenance

`Provenance` preserves, when available:

- source registry key (`source`);
- external/source record identity (`external_id`);
- source/signal type;
- source URL/reference;
- publisher;
- `retrieved_at`;
- `published_at`;
- `effective_at` / source-updated time;
- raw/source identifier;
- document/field locator metadata;
- optional explicit quality metadata;
- legal/reuse metadata.

Publisher timestamps are normalized to UTC and malformed timestamps fail closed. The generic `signal_to_fact()` adapter maps normalized Signals to Evidence + FACT without making individual connectors know Evidence Graph internals. Existing source registry metadata is referenced for quality/freshness/reuse policy instead of cloning registry structures into the graph.

For document evidence, `locator` is deliberately generic and can contain fields such as `page`, `section`, `field`, `json_path`, or `xml_path`. V1 does not implement OCR or document AI.

## Freshness

Freshness treats publisher/source time separately from observation time:

1. `effective_at` when available;
2. otherwise `published_at`;
3. if neither publisher timestamp is available, freshness is **unknown**.

`retrieved_at` proves when ObraSignal observed the record; it is never used as a substitute for publisher freshness. This prevents an old or undated publication from becoming apparently current merely because ObraSignal fetched it today. A future publisher timestamp is likewise treated as unknown freshness rather than false-fresh. Source-specific `stale_after_minutes` is reused from `source_registry.py`; the policy has an explicit positive fallback when the source has no registered threshold.

When freshness cannot be established, `explain()` includes `source_freshness` in its missing indicators and confidence is degraded. Historical nodes are retained. A stale claim is marked `STALE`; it is not deleted.

## Conflicts and supersession

Contradictions are first-class edges. If two supported deadline claims disagree, both can remain in the graph and `CONFLICT` is exposed to the consumer. V1 deliberately does not invent a universally valid source-winner hierarchy.

A policy can use source quality, recency, or domain-specific authority in a future resolver, but an unresolved disagreement remains visible.

Supersession preserves both versions. `new_claim -> old_claim : SUPERSEDES` marks the old claim `SUPERSEDED` without mutating or deleting it.

## Deduplication

Evidence is deduplicated by publisher-native provenance identity, publisher semantic timestamps, locator/field and value. Re-reading the same publisher revision — including a later `retrieved_at` caused only by retry/re-observation — does not produce another independent evidence node and therefore cannot increase confidence through duplication.

A publisher revision with a different `effective_at`/`published_at` remains a distinct evidence node even when the field value did not change. This preserves lifecycle history rather than silently retaining stale provenance for a genuinely revised record.

V1 does not attempt semantic cross-publisher entity resolution. Two genuinely different records that mirror the same upstream document require a future canonical-document identity adapter if the existing source identity cannot express that relationship.

## Confidence

Confidence is deliberately ordinal: `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`.

It is an auditable policy heuristic, not a probability. The default policy considers:

- registered source quality;
- presence/absence of evidence;
- number of assumptions;
- contradictions;
- staleness or unknown source freshness;
- transformation depth.

A directly supported FACT from a registered official, machine-verified, reuse-green source can reach `HIGH` when freshness is established. Unsupported and unknown material claims return `UNKNOWN`. Assumptions, conflicts, staleness, unknown freshness, and deeper transformations degrade confidence.

The policy is versioned (`evidence-policy-v1`) so it can later be replayed or replaced without pretending historical scores used a different rule.

## Status model

Material claims can be:

- `SUPPORTED`;
- `UNSUPPORTED`;
- `CONFLICT`;
- `STALE`;
- `UNKNOWN`;
- `SUPERSEDED`.

A FACT without evidence is `UNSUPPORTED`. An ESTIMATE or INFERENCE without dependencies is `UNSUPPORTED`. A `None` value is `UNKNOWN`. Unknown freshness does not masquerade as `STALE` or as proven freshness; it is represented in the explanation's missing indicators.

## Explanation contract

`EvidenceGraph.explain(claim_id, as_of=...)` returns a domain structure rather than user-facing prose. It contains:

- the requested claim;
- status;
- confidence;
- supporting FACTS;
- ESTIMATES;
- INFERENCES;
- ASSUMPTIONS;
- evidence provenance suitable for SHOW ME;
- conflicts;
- explicit missing support/value/freshness indicators;
- dependency IDs suitable for future WHAT-IF traversal;
- model and policy versions.

A UI or future narrative layer can render this structure. No LLM is required to calculate lineage, status, confidence, or dependencies.

## Signal integration

`signal_to_fact()` is intentionally connector-independent. A normalized Signal supplies existing canonical fields such as:

- `source`;
- `signal_type`;
- `external_id`;
- `url`;
- `source_reference`;
- `published_at` / `publication_date`;
- `source_updated_at`;
- `last_observed`.

The adapter creates evidence provenance and a supported FACT for the selected field. Connectors remain unchanged.

## Economic Fit integration demonstration

`economic_fit_lineage()` demonstrates the contract without rewriting `economic_fit.py`. The adapter records every material input used by the current economic-fit rule family:

- opportunity `value` always;
- `deadline` when deadline rules are configured;
- `procedure_type` when procedure rules are configured;
- profile assumptions for min/max value, deadline bounds, threshold, preferred procedures, and excluded procedures when present;
- the deterministic rule trace returned by `evaluate_economic_fit()` in estimate metadata.

Missing material Signal inputs are represented as explicit `FACT` claims with `value=None` and `metadata.missing=true`; absence is not silently converted into zero/false.

```text
OFFICIAL SIGNAL fields
        |
        v
     EVIDENCE
        |
      SUPPORTS
        v
       FACTS ------------------+
                                |
COMPANY PROFILE ASSUMPTIONS ----+--> ESTIMATE economic_fit.score
                                      |
                                   DERIVED_FROM
                                      v
                                  INFERENCE economic_fit.assessment
```

Calling `explain()` on the inference reconstructs the source evidence, facts, assumptions, score calculation metadata/rule trace, and dependency chain.

This is **decision support**, not a new Decision Ledger and not a claim that opportunity value equals value created by ObraSignal.

## Tenant isolation

`tenant_id` is mandatory and blank/default tenant fallback is forbidden. Every node ID incorporates the validated tenant identity, and graph instances reject cross-graph endpoint references. In-memory graphs therefore cannot accidentally connect Company A nodes to Company B nodes through the supported API.

This is an application-level V1 boundary only. There is no new persistence layer in this work, so no database row-level security or persistent tenant-isolation claim is made.

## Bounded execution

The in-process graph is explicitly bounded. Defaults are 10,000 nodes and 50,000 edges per graph instance, with positive constructor overrides available to a trusted caller. New nodes/edges fail closed once the configured bound is reached; existing graph state is preserved.

Identifiers/labels/URLs are length-bounded, locators/claim metadata/values are size-bounded, and a single serialized material value is capped at 256 KiB. Traversal is iterative for reachability, ancestry and depth so long legal chains do not rely on Python recursion depth.

## Security properties

Evidence text, labels, locators, URLs, and values are treated as data. The graph executes none of them and performs no templating, SQL construction, deserialization of arbitrary object graphs, URL fetching, or HTML rendering.

Tenant identity, publisher timestamps, mappings and graph capacity fail closed when malformed. Presentation consumers must continue to escape untrusted text/URLs according to their rendering context.

## Capability state

`capability_registry.py` already contains the pre-existing `EVIDENCE` capability in `EXPERIMENT` state with feature flag `evidence_graph_v1`. This branch does not promote or enable it and does not alter that registry entry.

`master_execution_queue.py` is intentionally untouched. `Q080_EVIDENCE_GRAPH_V1` remains under canonical queue control.

## Limitations

- In-memory only; no durability claim.
- Conflict detection is represented explicitly but not automatically inferred from arbitrary predicates/values.
- Supersession is explicit rather than automatically selected.
- Confidence is ordinal policy logic, not Bayesian probability.
- No semantic mirror-detection across unrelated source identities.
- No public API or production UI.
- No automatic Decision Ledger write.
- No persisted immutable decision snapshot/WORM store; immutability is guaranteed for node snapshots while in a graph.

## Future extensions

Explicitly outside v1:

- full WHAT-IF simulator;
- LLM narrative explanations;
- graph database;
- cross-company benchmark evidence;
- legal opinion engine;
- automatic dispute resolution;
- probabilistic/Bayesian graph;
- advanced causal inference;
- persistent decision snapshot adapter.

## Integration notes

The safest next integration step after review is to have one internal decision-support consumer instantiate an `EvidenceGraph`, convert already-normalized Signals through `signal_to_fact()`, attach deterministic scoring dependencies, and hand the `explain()` structure to presentation code behind the existing `evidence_graph_v1` feature flag.

That integration should occur only through the canonical Master Execution Queue. This parallel branch is preparation, not promotion.
