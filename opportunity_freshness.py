"""Deterministic opportunity freshness assessment for ObraSignal.

Freshness is deliberately separate from source connector health and lifecycle.
The evaluator performs no network calls and mutates neither opportunity nor
source state. All temporal decisions are made from injected inputs and policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping

from source_registry import SOURCES


POLICY_VERSION = "opportunity-freshness-v0"
FRESHNESS_ORDER = {"FRESH": 0, "AGING": 1, "STALE": 2, "UNKNOWN": 3}
MAX_SOURCE_ID_LENGTH = 128
MAX_OPPORTUNITY_ID_LENGTH = 512

SIGNAL_MULTIPLIER = {
    "TENDER": 1.0,
    "PROCUREMENT_PLAN": 4.0,
    "FORECAST": 4.0,
    "CAPITAL_PROJECT": 3.0,
    "MARKET_DIALOGUE": 2.0,
    "CONTRACT_EXPIRY": 2.0,
    "AWARD": 1.0,
    "CONTRACT": 1.0,
}


@dataclass(frozen=True)
class FreshnessPolicy:
    source: str
    signal_type: str
    expected_refresh_minutes: int
    aging_after_minutes: int
    stale_after_minutes: int
    failure_tolerance: int = 1
    unavailable_after_failures: int = 3
    near_deadline_minutes: int = 2880
    near_deadline_multiplier: float = 0.5
    policy_source: str = "registry"
    archival: bool = False


@dataclass(frozen=True)
class OpportunityFreshnessAssessment:
    opportunity_id: str | None
    source_id: str | None
    published_at: str | None
    source_updated_at: str | None
    last_observed_at: str | None
    last_successful_fetch_at: str | None
    last_failed_fetch_at: str | None
    observation_age_minutes: float | None
    source_update_age_minutes: float | None
    freshness_status: str
    source_health_status: str
    confidence: str
    reason_codes: tuple[str, ...]
    generated_at: str
    policy_version: str
    policy_source: str

    def to_dict(self):
        return asdict(self)


def _identifier(value, *, field, max_length):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field}")
    return text


def _utc(value, *, field):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid {field} timestamp") from exc
    else:
        raise ValueError(f"invalid {field} timestamp")
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _age_minutes(now, value):
    if value is None:
        return None
    delta = (now - value).total_seconds() / 60
    if delta < 0:
        raise ValueError("future timestamp")
    return delta


def policy_for(source: str | None, signal_type: str | None) -> FreshnessPolicy:
    source_key = _identifier(source, field="source", max_length=MAX_SOURCE_ID_LENGTH) or ""
    signal = str(signal_type or "TENDER").strip().upper() or "TENDER"
    meta = SOURCES.get(source_key)
    multiplier = SIGNAL_MULTIPLIER.get(signal, 1.0)

    if meta:
        expected = int(meta["expected_refresh_minutes"])
        stale = int(meta["stale_after_minutes"] * multiplier)
        aging = max(expected, int(stale / 2))
        return FreshnessPolicy(
            source=source_key,
            signal_type=signal,
            expected_refresh_minutes=expected,
            aging_after_minutes=aging,
            stale_after_minutes=max(aging + 1, stale),
            policy_source="source_registry",
            archival=signal in {"AWARD", "CONTRACT"},
        )

    # Explicit conservative fallback. Unknown source health remains UNKNOWN.
    expected = 1440
    stale = int(4320 * multiplier)
    return FreshnessPolicy(
        source=source_key,
        signal_type=signal,
        expected_refresh_minutes=expected,
        aging_after_minutes=max(expected, int(stale / 2)),
        stale_after_minutes=stale,
        policy_source="fallback_conservative",
        archival=signal in {"AWARD", "CONTRACT"},
    )


def _health_status(source_health: Mapping | None, *, now: datetime, policy: FreshnessPolicy):
    if not source_health:
        return "UNKNOWN", ()

    try:
        failures = max(0, int(source_health.get("consecutive_failures") or 0))
    except (TypeError, ValueError):
        return "UNKNOWN", ("INVALID_SOURCE_HEALTH",)
    try:
        last_success = _utc(source_health.get("last_success"), field="last_success")
        last_failed = _utc(source_health.get("last_failed") or (
            source_health.get("last_attempt") if failures else None
        ), field="last_failed")
        success_age = _age_minutes(now, last_success)
        _age_minutes(now, last_failed)
    except ValueError:
        return "UNKNOWN", ("INVALID_TIMESTAMP",)

    if failures >= policy.unavailable_after_failures:
        if success_age is None or success_age >= policy.stale_after_minutes:
            return "UNAVAILABLE", ("SOURCE_UNAVAILABLE",)
        return "DEGRADED", ("SOURCE_TEMPORARILY_DEGRADED",)
    if failures > 0:
        return "DEGRADED", ("SOURCE_TEMPORARILY_DEGRADED",)
    if last_success is None:
        return "UNKNOWN", ()
    if success_age is not None and success_age >= policy.stale_after_minutes:
        return "DEGRADED", ("SOURCE_TEMPORARILY_DEGRADED",)
    return "HEALTHY", ()


def evaluate_freshness(record_context: Mapping, source_context: Mapping | None = None, *, now: datetime, policy: FreshnessPolicy | None = None):
    """Evaluate freshness from already-observed state.

    ``retrieved_at`` is intentionally ignored as a freshness signal. Fetch time
    describes transport activity, not source publication/update semantics.
    """
    if not isinstance(record_context, Mapping):
        raise ValueError("record_context must be a mapping")
    if source_context is not None and not isinstance(source_context, Mapping):
        raise ValueError("source_context must be a mapping")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)

    source = _identifier(record_context.get("source"), field="source", max_length=MAX_SOURCE_ID_LENGTH)
    opportunity_id = _identifier(
        record_context.get("opportunity_id") or record_context.get("external_id"),
        field="opportunity_id",
        max_length=MAX_OPPORTUNITY_ID_LENGTH,
    )
    signal_type = str(record_context.get("signal_type") or "TENDER").strip().upper()
    policy = policy or policy_for(source, signal_type)
    reasons = []

    lifecycle = str(
        record_context.get("lifecycle_status")
        or record_context.get("source_status")
        or record_context.get("status")
        or ""
    ).strip().upper()
    explicitly_closed = lifecycle in {"CLOSED", "COMPLETE", "COMPLETED", "AWARDED", "CANCELLED", "CANCELED", "ARCHIVED"}

    try:
        published = _utc(record_context.get("published_at") or record_context.get("publication_date"), field="published_at")
        source_updated = _utc(record_context.get("source_updated_at"), field="source_updated_at")
        last_observed = _utc(record_context.get("last_observed_at") or record_context.get("last_observed"), field="last_observed_at")
        deadline = _utc(record_context.get("deadline") or record_context.get("target_date"), field="deadline")
        observation_age = _age_minutes(now, last_observed)
        source_update_age = _age_minutes(now, source_updated)
    except ValueError:
        health, health_reasons = _health_status(source_context, now=now, policy=policy)
        reasons.extend(health_reasons)
        reasons.append("INVALID_TIMESTAMP")
        return OpportunityFreshnessAssessment(
            opportunity_id=opportunity_id,
            source_id=source,
            published_at=None,
            source_updated_at=None,
            last_observed_at=None,
            last_successful_fetch_at=source_context.get("last_success") if source_context else None,
            last_failed_fetch_at=(source_context.get("last_failed") or source_context.get("last_attempt")) if source_context else None,
            observation_age_minutes=None,
            source_update_age_minutes=None,
            freshness_status="UNKNOWN",
            source_health_status=health,
            confidence="UNKNOWN",
            reason_codes=tuple(dict.fromkeys(reasons)),
            generated_at=now.isoformat(),
            policy_version=POLICY_VERSION,
            policy_source=policy.policy_source,
        )

    health, health_reasons = _health_status(source_context, now=now, policy=policy)
    reasons.extend(health_reasons)

    if explicitly_closed:
        reasons.append("EXPLICITLY_CLOSED")
        freshness = "UNKNOWN"
    elif policy.archival:
        reasons.append("ARCHIVAL_RECORD")
        freshness = "UNKNOWN"
    elif observation_age is None:
        reasons.append("INSUFFICIENT_TIMESTAMPS")
        freshness = "UNKNOWN"
    else:
        aging = policy.aging_after_minutes
        stale = policy.stale_after_minutes
        if deadline is not None and deadline >= now:
            deadline_minutes = (deadline - now).total_seconds() / 60
            if deadline_minutes <= policy.near_deadline_minutes:
                aging = max(policy.expected_refresh_minutes, int(aging * policy.near_deadline_multiplier))
                stale = max(aging + 1, int(stale * policy.near_deadline_multiplier))
                if observation_age >= aging:
                    reasons.append("DEADLINE_NEAR_WITH_OLD_OBSERVATION")

        if observation_age >= stale:
            freshness = "STALE"
            reasons.append("NO_RECENT_OBSERVATION")
        elif observation_age >= aging:
            freshness = "AGING"
            reasons.append("NO_RECENT_OBSERVATION")
        else:
            freshness = "FRESH"
            reasons.append("RECENTLY_OBSERVED")

    if source_update_age is not None and source_update_age >= policy.stale_after_minutes:
        reasons.append("SOURCE_UPDATE_OLD")

    confidence = "HIGH"
    if freshness == "UNKNOWN":
        confidence = "UNKNOWN"
    elif policy.policy_source != "source_registry" or health == "UNKNOWN":
        confidence = "LOW"
    elif source_updated is None or published is None:
        confidence = "MEDIUM"

    return OpportunityFreshnessAssessment(
        opportunity_id=opportunity_id,
        source_id=source,
        published_at=published.isoformat() if published else None,
        source_updated_at=source_updated.isoformat() if source_updated else None,
        last_observed_at=last_observed.isoformat() if last_observed else None,
        last_successful_fetch_at=source_context.get("last_success") if source_context else None,
        last_failed_fetch_at=(source_context.get("last_failed") or source_context.get("last_attempt")) if source_context else None,
        observation_age_minutes=round(observation_age, 1) if observation_age is not None else None,
        source_update_age_minutes=round(source_update_age, 1) if source_update_age is not None else None,
        freshness_status=freshness,
        source_health_status=health,
        confidence=confidence,
        reason_codes=tuple(dict.fromkeys(reasons)),
        generated_at=now.isoformat(),
        policy_version=POLICY_VERSION,
        policy_source=policy.policy_source,
    )


def assess_signal_record(conn, source: str, external_id: str, signal_type: str = "TENDER", *, now: datetime):
    """Read existing canonical/source-health state and evaluate on demand."""
    from signal_store import get_signal_record
    from source_health import ensure_source_health

    record = get_signal_record(conn, source, external_id, signal_type)
    if not record:
        return None
    ensure_source_health(conn)
    row = conn.execute("SELECT * FROM source_health WHERE source=?", (source,)).fetchone()
    health = dict(row) if row else None
    return evaluate_freshness(record, health, now=now)
