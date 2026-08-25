# ObraSignal Proof / Evidence Graph v1

## Purpose

Evidence Graph v1 is the deterministic provenance layer behind **WHY?**, **SHOW ME.**, and future **WHAT IF?** decision support. It does not replace Signals, the decision log, or source registries.

## Architecture

The graph itself is an in-process bounded directed graph. No graph database, second runtime, or new persistence table is introduced. A graph is built from already-normalized Signal fields plus account-scoped company-profile assumptions, then exported as an immutable detached snapshot.

The durable boundary is the existing append-only `opportunity_decisions.features_json`: when the `EVIDENCE` capability is enabled, each recorded commercial decision stores a `decision_evidence` snapshot tied to the exact decision/rule execution. The customer-facing explanation receives only a compact redacted `explanation.evidence` view. The private graph/profile snapshot is never copied into the API presentation row.

`DECISION` remains outside the Evidence node taxonomy. Decisions consume evidence-backed claims and persist the resulting lineage beside the existing decision record.

## Contract

Node types: `EVIDENCE`, `FACT`, `ESTIMATE`, `INFERENCE`, `ASSUMPTION`.

Edge types: `SUPPORTS`, `DERIVED_FROM`, `DEPENDS_ON`, `USES_ASSUMPTION`, `CONTRADICTS`, `SUPERSEDES`.

Material claims expose explicit status: `SUPPORTED`, `UNSUPPORTED`, `CONFLICT`, `STALE`, `UNKNOWN`, or `SUPERSEDED`. Missing data remains missing; it is never silently converted to zero, false, or low confidence.

Claims and evidence preserve stable identity, source/native record identity, publisher, source reference/URL, publisher/effective timestamps, observation timestamp, field/document locator, calculation/model/policy version and transformation lineage where available.

## Identity, deduplication and lifecycle

IDs are derived from canonical material content plus validated tenant identity. Re-observing the same publisher revision does not create independent evidence merely because `retrieved_at` changed. A publisher revision with a different semantic publisher/effective timestamp remains distinct even when the field value is unchanged.

Supersession preserves both versions. Contradictions remain explicit; v1 does not silently choose a winner.

## Freshness and confidence

Publisher freshness uses `effective_at`, then `published_at`. `retrieved_at` proves observation only and is never substituted for publisher freshness. Unknown or future publisher freshness degrades confidence instead of being called fresh.

Confidence is ordinal (`HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`) and versioned policy, not probability. Source quality, missing support, assumptions, conflicts, staleness/unknown freshness and transformation depth are visible inputs.

## Economic decision lineage

The production integration records the material inputs used by deterministic commercial/economic scoring:

```text
NORMALIZED SIGNAL
      |
      v
   EVIDENCE -> FACTS --------+
                              |
COMPANY PROFILE -> ASSUMPTIONS+--> ESTIMATE / INFERENCE
                                      |
                                      v
                              COMMERCIAL DECISION
                                      |
                                      v
                         append-only decision snapshot
```

Both canonical decision-recording paths use the same Evidence integration. The account identity used to load the profile is the same account identity written to the decision log.

If Evidence construction cannot satisfy its contract, the commercial decision remains available but Evidence is marked unavailable; the system does not manufacture support.

## Persistence and tenant safety

`tenant_id` is mandatory; blank/default fallback is forbidden in Evidence and decision persistence. The durable snapshot lives only inside the account-scoped decision row. No new globally queryable Evidence table exists.

`features_json` is bounded to 512 KiB. Evidence graphs are bounded by node/edge limits and material values/payloads are size-bounded. Traversal is iterative to avoid recursion amplification.

## Product presentation

The authenticated opportunity detail API reuses its existing account-scoped decision lookup. When Evidence is enabled, `explanation.evidence` may contain only the redacted presentation contract: state/confidence, source/field provenance, missing evidence and conflict count. It does not contain the private graph, tenant identifier or company-profile assumptions.

The existing web opportunity detail and mobile explanation surface render this redacted contract. Web source links are emitted only for absolute HTTP(S) URLs.

## Rollout and rollback

Capability registry state remains `EXPERIMENT` with feature flag `evidence_graph_v1` until canonical Q080 promotion is justified.

Runtime controls:

- `OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1=true` explicitly enables the experiment;
- `OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1=true` always disables presentation/creation;
- malformed rollout values fail closed;
- production deployment configuration declares the feature disabled by default;
- the health endpoint reports only safe enabled/disabled/error-class state, never environment values.

The read boundary checks rollout state on every presentation. Therefore the kill switch hides already-persisted Evidence immediately without deleting decision history. Rollback is configuration-only: set the feature false or kill switch true; no data migration or destructive cleanup is required.

## Security

Evidence material is data only. The graph executes no evidence text, HTML, URLs, SQL, templates, arbitrary object deserialization or network fetches. Tenant identity, timestamps, graph capacity and persisted payload bounds fail closed.

Customer presentation is deliberately narrower than the durable snapshot. Source URLs in the web presentation are restricted to HTTP(S).

## Observability

`GET /api/v1/health` reports the effective Evidence runtime state and whether rollout configuration is malformed. It does not expose flag values or secrets. Decision history itself preserves the evidence state and exact snapshot used when enabled.

## Testing obligations

The capability is not considered integrated merely because domain tests pass. The integration suite covers graph invariants, malformed timestamps, retry dedupe, publisher revisions, tenant isolation, bounded persistence, both decision paths, API redaction, read-time kill switch, web URL safety, mobile wiring and rollout observability. Exact-head Python and mobile CI remain required after every delivery change.

## Capability / queue truth

This branch does **not** change `master_execution_queue.py` and does not claim `Q080` complete. It does not claim deployment or production activation. Promotion is valid only after the foundation and product/runtime delta are semantically integrated in canonical order and exact-head validation passes on the integrated commit.

## V1 limitations

- No graph database or independent Evidence query service.
- No automatic semantic mirror detection across unrelated publishers.
- Conflict resolution is explicit policy work; unresolved conflicts remain visible.
- Confidence is an auditable ordinal heuristic, not Bayesian probability.
- WHAT-IF traversal inputs are preserved, but a full scenario simulator is outside Q080 v1.
- No LLM is required or trusted for lineage/status/confidence calculation.

## Integration order

1. Integrate the Evidence Graph domain foundation (#147) after semantic reconciliation with current `main`.
2. Integrate the dependent product/runtime persistence and presentation delta (#194).
3. Run exact-head Python/mobile/architecture gates on the resulting canonical commit.
4. Verify deployment configuration remains disabled by default.
5. Only then promote the capability/queue if the canonical Definition of Done is satisfied.
