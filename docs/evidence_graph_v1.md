# ObraSignal Proof / Evidence Graph v1

## Purpose

Evidence Graph v1 is the deterministic provenance layer behind **WHY?**, **SHOW ME.**, and future **WHAT IF?** decision support. It does not replace Signals, the decision log, source registries, authentication, or commercial scoring.

## Architecture

The graph itself is an in-process bounded directed graph. No graph database, second runtime, or new persistence table is introduced. A graph is built from already-normalized Signal fields plus account-scoped company-profile assumptions, then exported as an immutable detached snapshot.

The durable boundary is the existing append-only `opportunity_decisions.features_json`: when the `EVIDENCE` capability is enabled, each recorded commercial decision stores a `decision_evidence` snapshot tied to the exact decision/rule execution. The customer-facing explanation receives only a compact redacted `explanation.evidence` view. The private graph/profile snapshot is never copied into the API presentation row.

`DECISION` remains outside the Evidence node taxonomy. Decisions consume evidence-backed claims and persist the resulting lineage beside the existing decision record.

## Contract

Node types: `EVIDENCE`, `FACT`, `ESTIMATE`, `INFERENCE`, `ASSUMPTION`.

Edge types: `SUPPORTS`, `DERIVED_FROM`, `DEPENDS_ON`, `USES_ASSUMPTION`, `CONTRADICTS`, `SUPERSEDES`.

Material claims expose explicit status: `SUPPORTED`, `UNSUPPORTED`, `CONFLICT`, `STALE`, `UNKNOWN`, or `SUPERSEDED`. Missing data remains missing; it is never silently converted to zero, false, or low confidence.

Claims and evidence preserve stable identity, source/native record identity, publisher when supplied, source reference/URL, publisher/effective timestamps, observation timestamp, field locator, calculation/model/policy version and transformation lineage where available.

The authenticated customer policy is intentionally stricter than raw structural graph support: a material missing decision input or unknown publisher freshness cannot be returned as `SUPPORTED`, and a contradiction anywhere in the exposed decision lineage is returned as `CONFLICT`. This presentation policy is versioned separately as `decision-evidence-customer-v1`.

## Identity, deduplication and lifecycle

IDs are derived from canonical material content plus validated tenant identity. Re-observing the same publisher revision does not create independent evidence merely because `retrieved_at` changed. A publisher revision with a different semantic publisher/effective timestamp remains distinct even when the field value is unchanged.

Supersession preserves both versions. Contradictions remain explicit; v1 does not silently choose a winner.

## Freshness and confidence

Publisher freshness uses `effective_at`, then `published_at`. `retrieved_at` proves observation only and is never substituted for publisher freshness. Unknown or future publisher freshness is exposed as unknown rather than being called fresh.

Confidence is ordinal (`HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`) and versioned policy, not probability. Source quality, missing support, assumptions, conflicts, staleness/unknown freshness and transformation depth are visible inputs.

## Economic decision lineage

The product integration records material inputs used by deterministic commercial/economic scoring:

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

Missing source fields are explicit. Missing company specialization is also exposed rather than being interpreted as a negative fact. If Evidence construction cannot satisfy its contract, the commercial decision remains available but Evidence is marked unavailable; the system does not manufacture support.

## Persistence and tenant safety

`tenant_id` is mandatory at the Evidence boundary and blank tenant identity fails closed. Authenticated product paths derive account identity from the trusted server authentication context; request payload/query tenant identifiers are not used to select private Evidence.

The durable snapshot lives only inside the account-scoped decision row. No new globally queryable Evidence table exists. Legacy decision-store defaults remain for backwards compatibility, but blank identity is never converted into a default tenant by the Evidence integration.

`features_json` is bounded to 512 KiB. Evidence graphs are bounded by node/edge limits and material values/payloads are size-bounded. Traversal is iterative to avoid recursion amplification.

Before persistence, the product adapter validates the **combined** decision feature envelope. If an Evidence snapshot alone would push an otherwise-valid decision over 512 KiB, the core decision is preserved and Evidence is stored as an explicit `UNAVAILABLE / evidence_payload_too_large` marker. The graph is never silently truncated. If the baseline decision payload itself is oversized, the canonical decision-log size failure still applies.

## Product presentation

The authenticated opportunity API reuses its existing account-scoped decision lookup. When Evidence is enabled, `explanation.evidence` contains only the customer-safe contract: state/status/confidence, source and source-native reference, publisher when available, safe source URL when valid, field provenance, publisher/effective/retrieval timestamps, missing evidence, conflict count and policy/model versions.

The private graph, tenant identifier, raw company-profile snapshot, normalized private capability data and arbitrary internal metadata are not copied into that response.

Customer source URLs are filtered server-side and only absolute HTTP(S) URLs with a host are retained. Unsafe schemes, relative URLs and control-character-bearing URLs are removed from the customer contract. No Evidence URL is auto-fetched.

The existing web opportunity detail and mobile explanation surface consume the same customer-safe semantics. Mobile presents confidence, source/reference, missing evidence and conflicts rather than graph internals. Web rendering escapes untrusted content and independently refuses unsafe opportunity source links.

## Rollout and kill switch

Capability registry state remains `EXPERIMENT` with feature flag `evidence_graph_v1` until canonical Q080 promotion is separately justified.

Runtime controls:

- `OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1=true` explicitly enables the experiment;
- `OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1=true` always disables creation/presentation;
- malformed rollout values fail closed;
- production deployment configuration declares the feature disabled by default.

The read boundary checks rollout state on every presentation. Therefore the kill switch hides already-persisted Evidence immediately without deleting decision history. The generic health endpoint does not claim Evidence readiness or production activation.

## Security

Evidence material is data only. The graph executes no evidence text, HTML, URLs, SQL, templates, arbitrary object deserialization or network fetches. Tenant identity, timestamps, graph capacity and persisted payload bounds fail closed.

Customer presentation is deliberately narrower than the durable snapshot. Server-side URL filtering and frontend escaping are defense in depth; frontend hiding is not treated as redaction.

## Observability

Evidence construction logs safe source/external-identifier categories when contract validation rejects a snapshot and logs rollout configuration failure without exposing environment values, tokens, tenant-private profile data or raw Evidence payloads. Evidence observability does not turn the generic service health endpoint into a capability-readiness claim.

## Testing obligations

The capability is not considered integrated merely because domain tests pass. The integration suite covers graph invariants, malformed timestamps, retry dedupe, publisher revisions, tenant isolation, bounded persistence, both decision paths, non-default tenant profile lookup, customer redaction, server-side URL filtering, missing specialization, read-time kill switch, web injection/unsafe URL handling and mobile wiring. Exact-head Python and mobile CI remain required after every delivery change.

## Capability / queue truth

This branch does **not** change `master_execution_queue.py` and does not claim canonical `Q080 DONE`. It does not claim deployment or production activation. Promotion is valid only after the foundation and product/runtime delta are semantically integrated in canonical order and exact-head validation passes on the integrated commit.

## V1 limitations

- No graph database or independent Evidence query service.
- No automatic semantic mirror detection across unrelated publishers.
- Conflict resolution is explicit policy work; unresolved conflicts remain visible.
- Confidence is an auditable ordinal heuristic, not Bayesian probability.
- WHAT-IF traversal inputs are preserved, but a full scenario simulator is outside Q080 v1.
- No LLM is required or trusted for lineage/status/confidence calculation.
- Evidence does not perform publisher fetches; source-live validation belongs to connector/runtime ownership.

## Integration order

1. Integrate the Evidence Graph domain foundation (#147) after semantic reconciliation with current `main`.
2. Integrate the dependent product/runtime persistence and presentation delta (#194).
3. Reconcile the auth/deployment overlap semantically; preserve the canonical auth owner rather than selecting `render.yaml` wholesale.
4. Run exact-head Python/mobile/architecture gates on the resulting canonical combination.
5. Verify deployment configuration remains disabled by default.
6. Only then consider capability/queue promotion as a separate authorized governance action.

## Rollback

Disable Evidence immediately with the feature flag or kill switch, or revert the #194 product/runtime delta after integration. Existing decisions remain readable because no Evidence table/schema is required and old decisions without Evidence are supported. Already-persisted Evidence snapshots may safely remain in historical `features_json`; the read-time gate prevents customer exposure while disabled. Reverting #147 removes only the reusable in-process domain files after dependent #194 code is also removed/reverted.
