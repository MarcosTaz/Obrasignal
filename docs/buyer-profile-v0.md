# Buyer Profile Snapshot v0

## PURPOSE

Buyer Profile Snapshot v0 answers a deliberately bounded question: **who is this procuring entity, and what procurement activity is currently known to ObraSignal for that entity?**

It is an on-demand read model over normalized ObraSignal signals. It does not create a second procurement source of truth and it does not claim to represent the buyer's complete real-world activity.

Core product rule: **KNOWN ACTIVITY != TOTAL ACTIVITY.**

## NON-GOALS

V0 does not implement CRM, contacts, email/phone discovery, relationship management, lead/deal stages, private notes, outreach, web enrichment, LinkedIn discovery, payment behaviour, buyer risk, competitor scoring, future procurement prediction, supplier/buyer graphs, decision-maker graphs, or a complete Buyer Graph.

## BUYER IDENTITY

Repository inspection found no dedicated canonical `Organization`/`Buyer` registry in the current tree. The durable Signal contract currently stores buyer display text plus source/country and retains the complete normalized product record in `normalized_json`.

V0 therefore uses the strongest identity already present in each normalized record:

1. an explicit buyer/organization/contracting-authority/procuring-entity/purchaser/issuer identifier, when present; otherwise
2. a **name-scoped identity** containing source + jurisdiction + exact buyer name.

A name-scoped identity is intentionally weaker and is labelled as such in coverage notes. It must not be interpreted as a verified organization mapping.

## CANONICALIZATION

No fuzzy merge is performed.

- Same textual name in different jurisdictions remains distinct.
- Similar department names remain distinct.
- Distinct official identifiers remain distinct even if names are identical.
- Name variants carrying the same explicit identifier can resolve to the same snapshot within the same source/jurisdiction scope.

This is conservative by design. When a canonical Organization service is introduced, Buyer Profile should consume that contract rather than create a competing organization model.

## SNAPSHOT CONTRACT

`build_buyer_profile_snapshot(buyer_id, window, context)` returns a `BuyerProfileSnapshot` with:

- buyer identity and canonical display name;
- known identifiers and jurisdiction;
- known locations from observed buyer-associated records;
- known opportunity/award/contract counts;
- observed lot count;
- published opportunity, award and contract values separated by currency;
- known opportunity categories using existing taxonomy/code fields;
- bounded recent activity;
- observed date range;
- source references;
- explicit coverage notes;
- generated timestamp and `buyer-profile.v0` snapshot version.

V0 computes this on demand and creates no snapshot table/cache.

## OBSERVED ACTIVITY SEMANTICS

Counts are always **known/observed counts**. Zero means that ObraSignal currently observes zero matching records in the selected window; it does not mean the buyer had no real-world procurement activity.

Opportunity deduplication prefers existing procedure-level identities in normalized data (`canonical_opportunity_id`, `procurement_id`, `procedure_id`, `ocid`, `tender_id`). It falls back to source + signal external ID only when no stronger procedure identity exists.

An original notice and amendment sharing a procedure identity count as one observed procedure. The latest observed version supplies its current published fields.

## LOT SEMANTICS

`known_opportunity_count` is procedure-level after canonical-key suppression. `observed_lot_count` is a separate metric containing distinct observed `lot_id`/`lot_identifier` values. Lots are not silently added to procedure counts.

## TIME WINDOWS

Supported deterministic windows are `12m`, `24m`, `all`, and `all_observed`.

Relative windows require an explicit clock internally; tests inject a fixed UTC instant. Records without a usable activity date are excluded from bounded 12/24-month metrics and may appear only in all-observed aggregation.

`observed_from` and `observed_to` describe the dated records included in the selected activity window, not the buyer's legal existence or complete procurement history.

## VALUE TYPES

Published values are never collapsed into one spend figure:

- `known_published_opportunity_values_by_currency`
- `known_award_values_by_currency`
- `known_contract_values_by_currency`

No field is called annual procurement spend, total spend, buyer budget, or entire procurement history.

## CURRENCY

Currencies are grouped independently. EUR 1M + GBP 1M remains two values. V0 has no FX engine and performs no currency conversion.

Malformed, missing or negative amounts are not invented or coerced into spend.

## CATEGORY BREAKDOWN

Only existing `taxonomy` and `category_code` values are used. Buyer Profile does not invent a new taxonomy or infer "strategic priorities". Category counts mean known opportunities observed with that category.

## COVERAGE LIMITATIONS

Every snapshot states that it reflects only normalized records currently available to ObraSignal and lists the observed source scope.

Coverage can change when sources, connectors or historical depth change. Therefore the snapshot carries an explicit version and observed period. Partial coverage is a first-class condition, not an error to conceal.

A current repository limitation is that the generic OCDS adapter normalizes buyer names but does not currently promote OCDS buyer identifiers into a dedicated Signal column. Buyer Profile can reuse an explicit identifier when a normalized record already contains one; otherwise it remains name-scoped rather than pretending the identity is verified.

## TENANT BOUNDARY

Buyer Profile v0 reads only shared normalized Signal records. The `context` parameter is reserved for future authorization/integration but v0 deliberately does not join company decisions, workflows, watchlists, outcomes, account notes or other tenant-private data.

Public procurement intelligence may be shared. Any future private enrichment must be explicitly tenant-scoped and must not leak into the global buyer snapshot.

## SOURCE PROVENANCE

Snapshots return bounded source/reference pairs from the records used for the selected activity window. The read model references source provenance instead of copying raw publisher payloads or private transport metadata.

## API

The domain contract is intentionally controller-independent. No public API route is wired in this isolated v0 branch because the current API has no canonical buyer reference on opportunity responses and exposing a name-search route would violate the identity rule. A future route such as `GET /api/v1/buyers/{buyer_id}` is safe once opportunity/read surfaces can carry the exact `buyer_id` returned by the identity contract and the existing rollout mechanism is wired end-to-end.

This is an integration boundary, not missing domain logic: frontend code must never reconstruct or search buyer profiles by fuzzy/textual name.

## UI

No new CRM-style UI is added in v0. A future contextual surface should use accessible sections such as Overview, Recent Activity, Known Opportunities, Known Awards/Contracts, Categories and Data Coverage. Copy must retain `Known`, `Observed`, and coverage qualifiers.

## SECURITY

Buyer IDs are structured, URL-safe encoded identities with a bounded maximum length and are decoded before parameterized SQL predicates are constructed. Malformed/oversized values fail closed. Organization names remain untrusted data; the domain layer returns data and does not render HTML.

The snapshot service performs SELECT-only reads. It neither mutates canonical Signal records nor reads tenant-private tables.

## PERFORMANCE

The service performs one bounded identity query followed by in-memory aggregation, avoiding N+1 reads. Name-scoped identities use indexed source/country columns plus exact buyer filtering. Strong identifiers currently retained only inside `normalized_json` may require scanning the source/jurisdiction candidate set; a canonical Organization/identifier index is a future optimization when justified by production evidence.

Recent activity is bounded to 1..50 records.

## TESTS

Focused tests cover:

- official identifier identity;
- same identifier with name variants;
- false merge prevention for distinct identifiers;
- same name/different jurisdiction;
- distinct departments;
- opportunity/award/contract aggregation;
- 12-month vs all-observed windows;
- category breakdown;
- currency separation;
- value-type separation;
- amendment/procedure deduplication;
- lot semantics;
- source refs and coverage notes;
- zero known activity semantics;
- deterministic output under a fixed clock;
- private-data isolation;
- canonical-record non-mutation;
- malformed, oversized and injection-like buyer IDs.

## KNOWN LIMITATIONS

- No repository-wide canonical Organization registry currently exists for buyer identity reuse.
- Buyer identifiers are not uniformly normalized across all existing connectors.
- No cross-source organization merge is attempted, even when two sources may refer to the same legal entity.
- Award/Contract usefulness depends on those signal types actually being present in the current Signal store.
- Buyer registered location is not separately modeled in the current Signal contract; v0 therefore reports `known_locations` from buyer-associated records and does not relabel project/opportunity places as verified registered addresses.
- No persistence/cache is added.
- No API/UI rollout is claimed.

These limitations prefer false negatives/unknowns over false identity or spend claims.

## FUTURE BUYER GRAPH INTEGRATION

A future Buyer Graph may consume stable Buyer Profile identity/provenance facts after a canonical Organization layer exists. It must not reverse this dependency by making the snapshot depend on a graph, relationship score, supplier graph, decision-maker graph or competitor model.

Possible future work, separately authorized: canonical organization registry, source adapter promotion of verified buyer identifiers, indexed identifier lookup, Evidence Graph links, data-quality/completeness annotations, cache/performance work, API/UI integration, and Buyer Graph relationships.
