"""Truth-preserving Customer Value read model.

This module consumes the existing Evaluation event store but deliberately keeps
product-generated availability, observed customer interaction, delivery evidence
and commercial outcomes as different facts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

VALUE_AVAILABLE_EVENT = "first_shortlist_generated"
OBSERVED_VALUE_EVENTS = frozenset({
    "relevant_opportunity_viewed",
    "evidence_viewed",
    "action_taken",
})
DELIVERY_EVIDENCE_EVENTS = frozenset({"alert_delivered"})
RETRY_BUCKET_SECONDS = 300


def _parse_iso(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _metadata(raw):
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _seconds_between(start, end):
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds()))


def _logical_observation_key(event_name, occurred_at, metadata):
    """Suppress obvious retry noise without erasing later genuine revisits.

    Five-minute buckets are intentionally conservative. Two identical route
    observations inside the same bucket count once; a later revisit can count
    again. Workflow transitions additionally carry status in the key.
    """
    bucket = int(occurred_at.timestamp()) // RETRY_BUCKET_SECONDS
    return (
        str(event_name),
        str(metadata.get("source") or ""),
        str(metadata.get("external_id") or ""),
        str(metadata.get("workflow_status") or metadata.get("to_status") or ""),
        bucket,
    )


def customer_value_summary(conn, account_id):
    """Return evidence states without converting availability into observed value."""
    account_id = str(account_id)
    row = conn.execute(
        "SELECT account_id, created_at FROM accounts WHERE account_id=?",
        (account_id,),
    ).fetchone()
    if row is None:
        raise ValueError("account_not_found")
    account = dict(row)
    created_at = _parse_iso(account.get("created_at"))

    rows = conn.execute(
        """SELECT id, event_name, occurred_at, metadata_json
           FROM evaluation_events WHERE account_id=? ORDER BY occurred_at, id""",
        (account_id,),
    ).fetchall()

    available_times = []
    observed = []
    delivery_times = []
    seen_observations = set()
    malformed_time_count = 0

    for raw_row in rows:
        item = dict(raw_row)
        event_name = str(item.get("event_name") or "")
        occurred_at = _parse_iso(item.get("occurred_at"))
        if occurred_at is None:
            malformed_time_count += 1
            continue
        metadata = _metadata(item.get("metadata_json"))
        if event_name == VALUE_AVAILABLE_EVENT:
            available_times.append(occurred_at)
            continue
        if event_name in DELIVERY_EVIDENCE_EVENTS:
            delivery_times.append(occurred_at)
            continue
        if event_name not in OBSERVED_VALUE_EVENTS:
            continue
        key = _logical_observation_key(event_name, occurred_at, metadata)
        if key in seen_observations:
            continue
        seen_observations.add(key)
        observed.append({
            "event_name": event_name,
            "occurred_at": occurred_at,
            "metadata": {
                key: metadata.get(key)
                for key in ("source", "external_id", "workflow_status", "from_status", "to_status")
                if metadata.get(key) not in (None, "")
            },
        })

    value_available_at = min(available_times) if available_times else None
    first_observed_at = observed[0]["occurred_at"] if observed else None
    repeat_observed_at = observed[1]["occurred_at"] if len(observed) >= 2 else None

    if repeat_observed_at:
        state = "REPEAT_VALUE_OBSERVED"
    elif first_observed_at:
        state = "FIRST_VALUE_OBSERVED"
    elif value_available_at:
        state = "VALUE_AVAILABLE"
    else:
        state = "UNPROVEN"

    ordering = "CONSISTENT"
    if first_observed_at and value_available_at and first_observed_at < value_available_at:
        ordering = "OBSERVED_BEFORE_AVAILABLE"
    elif first_observed_at and value_available_at is None:
        ordering = "AVAILABLE_EVIDENCE_MISSING"

    return {
        "account_id": account_id,
        "state": state,
        "value_available": value_available_at is not None,
        "value_available_at": value_available_at.isoformat() if value_available_at else None,
        "first_value_observed": first_observed_at is not None,
        "first_value_observed_at": first_observed_at.isoformat() if first_observed_at else None,
        "repeat_value_observed": repeat_observed_at is not None,
        "repeat_value_observed_at": repeat_observed_at.isoformat() if repeat_observed_at else None,
        "time_to_value_available_seconds": _seconds_between(created_at, value_available_at),
        "time_to_observed_first_value_seconds": _seconds_between(created_at, first_observed_at),
        "observed_interaction_count": len(observed),
        "delivery_evidence_count": len(delivery_times),
        "ordering": ordering,
        "malformed_event_time_count": malformed_time_count,
        "commercial_outcome": "UNPROVEN",
    }
