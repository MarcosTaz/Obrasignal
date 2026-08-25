# Source Health / Freshness Contract v1

Status: candidate contract for GAP-GP-011. This branch is not canonical until integration and Golden acceptance. No merge is implied.

## Purpose

Expose one public, source-specific truth contract derived from the existing canonical `source_health` persistence and `source_registry` policy. This contract does not create a second health store and does not rewrite opportunity lifecycle.

## Independent dimensions

Every source exposes two independent dimensions:

- `freshness`: `fresh | aging | stale | unknown`
- `health`: `healthy | degraded | unavailable | unknown`

Freshness is derived from the age of the last successful observation using that source's `expected_refresh_minutes` and `stale_after_minutes` registry policy. Health is derived from successful observation evidence, failure streaks and overdue observations.

A source can therefore be fresh but degraded after a recent failed attempt, or stale and degraded when no sufficiently recent successful observation exists. Persistent failures only become `unavailable` after bounded evidence; one transient failure is `degraded`, not `unavailable`.

## Source-level stats truth

`last_found` and `last_new_items` are statistics from the last successful source observation. Failed fetches no longer overwrite those values with zero.

`stats_state` qualifies those retained values:

- `current`: fresh + healthy successful observation;
- `aging`: successful observation has missed expected refresh but is inside the stale threshold;
- `stale`: retained values exist but health/freshness evidence is degraded, unavailable or stale;
- `unknown`: no valid successful observation proves the counts.

A stale/error count must never be rendered as a current zero.

## Coverage truth

Registry entries remain visible, but only sources whose canonical runtime status is `active` are counted as expected current ingestion coverage. `ready`, `planned`, `opt_in` and unknown sources do not falsely lower or raise active coverage.

The summary exposes:

- `coverage_status`;
- `expected_source_count`;
- `observed_expected_source_count`;
- `all_expected_sources_current`;
- `market_absence_proven=false`;
- `zero_market_claim_allowed=false`.

These last two fields are deliberately false. Source freshness can prove the state of configured observations; it cannot prove that the market itself contains zero opportunities.

## Public API

### `GET /api/v1/source-health-contract`

Authenticated public v1 read contract for Web/Mobile. Returns `contract_version=source-health-v1`, generated time, source items and coverage summary. Optional `?source=TED` scopes the contract to a single source.

### Legacy compatibility: `GET /api/v1/source-health`

This route already existed before GAP-GP-011 and remains unchanged as a compatibility endpoint returning observed `source_health` rows. Because it calls the same canonical `source_health_snapshot`, its items now receive additive `freshness`, `health` and `stats_state` fields. It does not enumerate missing registered sources or provide the v1 coverage summary.

The legacy route and the v1 route are not parallel truths: both derive from the same `source_health` table and `source_registry` policy. New Web/Mobile integration should consume `/source-health-contract` when it needs explicit coverage/missing-source truth.

### `GET /api/v1/opportunities`

The existing response is additive. It now includes:

- `source_coverage`;
- `source_health_contract_version`;
- `empty_result`.

`empty_result.state` is:

- `has_results` when the response contains opportunities;
- `observed_empty_current` only when the scoped expected source evidence is fresh + healthy;
- `coverage_unconfirmed` when an empty response is accompanied by aging/stale/unknown/degraded/unavailable coverage.

Even `observed_empty_current` remains bounded to loaded observations and never means zero market.

### `GET /api/v1/stats`

A successful stats response now includes `stats_state=current`, `source_coverage`, `source_health_contract_version` and `generated_at`.

The stats request and source-health-contract request are independent. This is intentional so a partial stats failure cannot be hidden by a successful opportunities/source-health request.

## Web / Mobile integration requirement

Consumers MUST keep a separate state for the stats request. If stats retrieval fails while opportunities or source health succeed, the client must surface stats as `error`, `stale` or `unknown` according to its cache state. It must not keep the previous number visually current, and it must not use successful source-health retrieval as proof that the stats request succeeded.

Consumers MUST use `empty_result` / `source_coverage` to qualify empty Radar states. They must not infer a zero-market statement from `items=[]`.

## Historical retention

Source failures update observability only. They do not delete, truncate or rewrite historical opportunities. Retained source counts likewise remain attached to their last successful observation and become explicitly stale when newer fetches fail.

## Migration / rollback

`ensure_source_health()` performs idempotent additive migration for `last_failed` and `consecutive_failures`. Existing rows are retained.

Rollback of API consumption is safe: stop consuming the additive fields/endpoint. The additive columns may remain unused. No opportunity history is rewritten by this contract.

## Integration Lab handoff

1. Reconstruct current main before composition.
2. Compose this candidate semantically with the current Web truth branch, including PR #298 or its successor; do not resolve overlaps by file-level winner selection.
3. Preserve Production Auth, tenant/account isolation and existing lifecycle/actionability semantics.
4. Wire Web/Mobile to `api.sourceHealth()` / `/api/v1/source-health-contract` and the additive `/opportunities` fields without importing private backend modules.
5. Prove partial stats failure disclosure independently from opportunity/source-health success.
6. Run exact-head Quality and the relevant Web/Mobile gates.
7. No canonical merge without explicit authorization.

## Golden Path handoff

GAP-GP-011 acceptance must prove at minimum:

1. fresh + healthy source with empty results -> bounded observed-data empty, never zero-market;
2. aging source -> aging disclosure;
3. stale source with empty results -> `coverage_unconfirmed`;
4. transient source failure -> degraded, prior counts/history retained and qualified stale;
5. persistent overdue failures -> unavailable;
6. missing source observation -> unknown;
7. stats request failure with opportunities/source-health success -> explicit partial-failure UI, no silently retained current stats;
8. historical opportunity remains inspectable after source degradation/unavailability;
9. Web and Mobile consume the public v1 API contract, not a parallel health truth.
