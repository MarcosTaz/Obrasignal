# Opportunity Source Health / Freshness v0

## PURPOSE

Answer a narrow decision question without live-fetching a source:

> Is this opportunity current/observable enough to rely on for a decision?

V0 provides a deterministic on-demand assessment over state ObraSignal already has. It does **not** claim that an opportunity is true/false, open/closed, or bid-ready.

## NON-GOALS

V0 does not build a connector observability platform, uptime dashboard, incident system, scraping fallback, failover, notification delivery, AI freshness prediction, or SRE analytics suite. It does not duplicate Data Quality, Change History, Evidence Graph, lifecycle inference, or bid-readiness logic.

## TIMESTAMP SEMANTICS

These timestamps are deliberately distinct:

- `published_at`: official publication time when the publisher exposes it.
- `source_updated_at`: publisher update time only when the source actually exposes that semantic.
- `retrieved_at`: transport/retrieval time. It is **not** used as evidence that publisher data changed.
- `last_observed` / `last_observed_at`: last valid observation of the same canonical source record.
- `last_success`: last successful source fetch; connector/runtime observability, not record update.
- `last_failed`: last failed source fetch; connector/runtime observability.
- `first_observed`: canonical Signal persistence time for the first valid observation.

`signal_records` already persists publication/update/observation semantics. `source_health` already persists source fetch state. V0 reuses those stores instead of creating a new freshness table.

Timezone-aware timestamps are normalized to UTC. Naive, malformed, or future timestamps fail closed to `UNKNOWN`/`INVALID_TIMESTAMP`; they never create negative age or false freshness.

## FRESHNESS VS SOURCE HEALTH

Freshness and source health are independent outputs.

Freshness status:

- `FRESH`: observation age is inside the active policy.
- `AGING`: observation age reached the warning boundary.
- `STALE`: ObraSignal has not confirmed the record recently enough for its policy/context.
- `UNKNOWN`: insufficient/invalid temporal evidence, or a lifecycle/archive case where freshness is not a useful truth claim.

Source health status:

- `HEALTHY`: recent successful observation and no current failure streak.
- `DEGRADED`: transient failures, recent-success/persistent-failure combinations, or overdue source observation.
- `UNAVAILABLE`: persistent failure streak plus no sufficiently recent success.
- `UNKNOWN`: insufficient or invalid source-health evidence.

A source failure does not itself make an opportunity stale. An opportunity can be fresh while the source is degraded, and stale while the connector is currently healthy.

## POLICY MODEL

`policy_for(source, signal_type)` derives the baseline from the canonical `source_registry.SOURCES` metadata:

- `expected_refresh_minutes`;
- `stale_after_minutes`;
- source identity;
- signal type.

The aging boundary is derived from source cadence/stale policy. No universal `7 days = stale` rule exists.

Unknown sources use an explicit conservative fallback policy. Their source-health result remains `UNKNOWN` unless health evidence is provided, and confidence is reduced.

The policy contract includes failure tolerance, unavailable failure streak, near-deadline window, near-deadline multiplier, archival semantics and policy source/version.

## SIGNAL-TYPE AWARENESS

Signal type changes freshness semantics:

- `TENDER`: baseline source policy.
- `PROCUREMENT_PLAN` / `FORECAST`: longer observation horizon than tenders.
- `CAPITAL_PROJECT` / `MARKET_DIALOGUE` / `CONTRACT_EXPIRY`: explicit extended horizons.
- `AWARD` / `CONTRACT`: archival semantics. Old age alone does not produce `STALE`.

The multipliers are policy configuration, not publisher timestamps fabricated by the evaluator.

## DEADLINE CONTEXT

For an active record whose deadline is within the near-deadline policy window, aging/stale thresholds tighten. The same observation age can therefore be `AGING` for a far-away tender and `STALE` for a tender closing soon.

Reason code `DEADLINE_NEAR_WITH_OLD_OBSERVATION` explains the contextual downgrade.

## UNKNOWN SEMANTICS

`UNKNOWN` means ObraSignal does not have enough safe temporal evidence to make a freshness claim. It does not mean bad data, closed, false, unavailable, or unusable.

Explicitly closed lifecycle states and archival award/contract records are not reclassified as stale by age alone. V0 returns `UNKNOWN` with `EXPLICITLY_CLOSED` or `ARCHIVAL_RECORD`, preserving lifecycle truth without inventing freshness.

## REASON CODES

V0 uses a deliberately small auditable set including:

- `RECENTLY_OBSERVED`
- `NO_RECENT_OBSERVATION`
- `SOURCE_UPDATE_OLD`
- `SOURCE_TEMPORARILY_DEGRADED`
- `SOURCE_UNAVAILABLE`
- `DEADLINE_NEAR_WITH_OLD_OBSERVATION`
- `INSUFFICIENT_TIMESTAMPS`
- `ARCHIVAL_RECORD`
- `EXPLICITLY_CLOSED`
- `INVALID_TIMESTAMP`
- `INVALID_SOURCE_HEALTH`

No false-precision numeric confidence score is produced. Confidence is `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`.

## SOURCE HEALTH FAILURE STREAK

`source_health` gains two backward-compatible additive fields:

- `last_failed TEXT`
- `consecutive_failures INTEGER DEFAULT 0`

`ensure_source_health()` adds them to an existing table without dropping/replacing legacy rows. Failure increments the streak; success resets it. This is the minimum state needed to distinguish one transient failure from prolonged inability to observe.

This is not a global incident platform.

## API / UI

V0 intentionally adds no new HTTP route or UI surface. Adding a read-path endpoint before canonical product wiring would increase coupling and security surface without improving the core correctness gate.

`assess_signal_record(conn, source, external_id, signal_type, now=...)` is the minimal integration seam for a future read model or `GET /api/v1/opportunities/{id}/freshness` endpoint. It reads canonical Signal/source-health state and performs no live network call.

Future copy should remain calm and factual, e.g.:

- `Last confirmed 2h ago. Source healthy.`
- `Last confirmed 9 days ago. Verify before relying on this deadline.`
- `ObraSignal could not confirm updates from this source recently.`

It must never say `Opportunity unavailable` merely because the source is temporarily unavailable.

## SECURITY

The evaluator:

- performs no SQL construction from user strings;
- performs no network calls;
- rejects non-mapping contexts;
- rejects control characters and oversized source/opportunity identifiers;
- treats bounded SQL metacharacters as inert data;
- fails invalid timestamp/health data closed;
- returns no raw HTML and executes no metadata;
- does not add tenant-private persistence or cross-tenant annotations.

Public-source freshness is global/shared by design. No company-private interpretation is introduced in v0.

## TESTS

Coverage includes:

- fresh / aging / stale source-aware evaluation;
- exact threshold boundaries;
- missing timestamps -> `UNKNOWN`;
- healthy / degraded / unavailable / unknown source health;
- isolated and persistent failures;
- failure streak reset after success;
- legacy `source_health` schema migration;
- historical award false-stale protection;
- closed tender false-stale protection;
- retrieved-today false-fresh protection;
- near-deadline contextual tightening;
- long-horizon planning policy;
- future / naive / malformed timestamp handling;
- UTC/timezone normalization;
- deterministic replay and no input mutation;
- monotonic freshness degradation with increasing observation age;
- malformed/oversized identifiers;
- SQL metacharacters as inert data;
- invalid source-health counters.

## CAPABILITY / FEATURE FLAG

This branch is a parallel implementation prepared for review. It does not modify the capability registry or create a feature flag because it is not wired into a runtime/API/UI path. Registering/enabling it before canonical queue integration would incorrectly imply rollout maturity.

## KNOWN LIMITATIONS

- Source policies inherit cadence values from the current source registry and therefore are only as accurate as that metadata.
- V0 has no historical health time series beyond last failure/success and consecutive-failure state.
- Amendment/corrigendum activity can improve future policy reasoning but is not independently modeled here.
- `source_updated_at` quality varies by connector/source and is only interpreted when already present.
- No alert/readiness notification is emitted.

## FUTURE ALERT / READINESS INTEGRATION

Future consumers may use the assessment as an input, not as a replacement for their own decision contract:

- Alerting: deadline near + stale, or source degraded/unavailable.
- Readiness: critical supporting data stale -> warning/unknown.
- Evidence: show timestamps, source refs and policy/reason codes.
- Change History: supply publisher update/amendment metadata; freshness does not implement diffing.

## INTEGRATION / ROLLBACK

Integration is additive. The evaluator is a new module; `source_health` schema evolution only adds nullable/defaulted columns. Existing source-health call sites remain compatible because clock injection parameters are optional.

Rollback can stop calling/removing `opportunity_freshness.py`; the added SQLite columns may safely remain unused. No canonical opportunity/signal record is mutated by an assessment.

Prepared in parallel. Does not modify the canonical Master Execution Queue, build a global connector-monitoring platform, or claim production integration.
