"""Value-aware ObraSignal evaluation lifecycle v0.1.

This module governs product evaluation access only. Paid ``pro`` entitlement remains
owned by the existing RevenueCat/store billing path in ``account_registry.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math

DEFAULT_EVALUATION_DAYS = 21
ENTERPRISE_PILOT_DAYS = 30
MAX_VALUE_EXTENSION_DAYS = 7

ACTIVATION_EVENTS = frozenset({
    "profile_ready",
    "market_data_available",
    "first_shortlist_generated",
})
VALUE_EXPOSURE_EVENTS = frozenset({
    "first_shortlist_generated",
    "relevant_opportunity_viewed",
    "deep_analysis_completed",
    "go_no_go_generated",
    "evidence_viewed",
    "alert_delivered",
    "action_taken",
})
ENGAGEMENT_EVENTS = frozenset({
    "relevant_opportunity_viewed",
    "deep_analysis_completed",
    "evidence_viewed",
    "action_taken",
})
ALLOWED_EVENTS = ACTIVATION_EVENTS | VALUE_EXPOSURE_EVENTS | frozenset({
    "paid_conversion",
    "post_conversion_churn",
})

EVALUATION_EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    metadata_json TEXT,
    UNIQUE(account_id, event_name, occurred_at)
)
"""


def _now(value=None):
    return value or datetime.now(timezone.utc)


def _parse_iso(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ensure_evaluation_schema(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    migrations = {
        "evaluation_type": "ALTER TABLE accounts ADD COLUMN evaluation_type TEXT",
        "evaluation_status": "ALTER TABLE accounts ADD COLUMN evaluation_status TEXT",
        "evaluation_activated_at": "ALTER TABLE accounts ADD COLUMN evaluation_activated_at TEXT",
        "evaluation_ends_at": "ALTER TABLE accounts ADD COLUMN evaluation_ends_at TEXT",
        "evaluation_extension_days": "ALTER TABLE accounts ADD COLUMN evaluation_extension_days INTEGER NOT NULL DEFAULT 0",
        "evaluation_value_status": "ALTER TABLE accounts ADD COLUMN evaluation_value_status TEXT",
        "evaluation_activation_reason": "ALTER TABLE accounts ADD COLUMN evaluation_activation_reason TEXT",
        "evaluation_extension_reason": "ALTER TABLE accounts ADD COLUMN evaluation_extension_reason TEXT",
    }
    for name, statement in migrations.items():
        if name not in columns:
            conn.execute(statement)
    conn.execute(EVALUATION_EVENT_SCHEMA)


def _insert_event(conn, account_id, event_name, occurred_at, metadata=None):
    conn.execute(
        "INSERT OR IGNORE INTO evaluation_events(account_id,event_name,occurred_at,metadata_json) VALUES(?,?,?,?)",
        (str(account_id), event_name, occurred_at.isoformat(), json.dumps(metadata or {}, separators=(",", ":"))),
    )


def _event_names(conn, account_id):
    rows = conn.execute(
        "SELECT DISTINCT event_name FROM evaluation_events WHERE account_id=?",
        (str(account_id),),
    ).fetchall()
    return {row[0] for row in rows}


def _duration_days(evaluation_type):
    return ENTERPRISE_PILOT_DAYS if evaluation_type == "enterprise" else DEFAULT_EVALUATION_DAYS


def record_evaluation_event(conn, account_id, event_name, *, metadata=None, occurred_at=None):
    """Record an auditable product event and advance lifecycle deterministically.

    Activation requires profile readiness, available market data and a first relevant
    shortlist. No future/unimplemented capability event is accepted by this v0.1 API.
    """
    event_name = str(event_name or "").strip()
    if event_name not in ALLOWED_EVENTS:
        raise ValueError(f"unsupported evaluation event: {event_name}")
    ensure_evaluation_schema(conn)
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    if not row:
        raise ValueError("account_not_found")
    account = dict(row)
    when = _now(occurred_at)
    _insert_event(conn, account_id, event_name, when, metadata)

    status = account.get("evaluation_status")
    if status in {None, "PAID", "CLOSED"}:
        conn.commit()
        return evaluation_summary(conn, dict(conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()), now=when)

    names = _event_names(conn, account_id)
    if event_name in VALUE_EXPOSURE_EVENTS:
        conn.execute(
            "UPDATE accounts SET evaluation_value_status=CASE WHEN evaluation_value_status IN (NULL,'EXPOSURE_PENDING') THEN 'EXPOSED' ELSE evaluation_value_status END WHERE account_id=?",
            (str(account_id),),
        )

    if not account.get("evaluation_activated_at"):
        if ACTIVATION_EVENTS.issubset(names):
            duration = _duration_days(account.get("evaluation_type"))
            end = when + timedelta(days=duration)
            conn.execute(
                """UPDATE accounts SET evaluation_status='EVALUATION_ACTIVE',
                   evaluation_activated_at=?, evaluation_ends_at=?,
                   evaluation_activation_reason=? WHERE account_id=?""",
                (when.isoformat(), end.isoformat(),
                 "profile_ready+market_data_available+first_relevant_shortlist_generated",
                 str(account_id)),
            )
        elif {"profile_ready", "market_data_available"}.issubset(names):
            conn.execute("UPDATE accounts SET evaluation_status='VALUE_READY' WHERE account_id=?", (str(account_id),))
        elif "profile_ready" in names:
            conn.execute("UPDATE accounts SET evaluation_status='PROFILE_READY' WHERE account_id=?", (str(account_id),))
        else:
            conn.execute("UPDATE accounts SET evaluation_status='ONBOARDING' WHERE account_id=?", (str(account_id),))
    conn.commit()
    fresh = dict(conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone())
    return evaluation_summary(conn, fresh, now=when)


def configure_enterprise_pilot(conn, account_id):
    ensure_evaluation_schema(conn)
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    if not row:
        raise ValueError("account_not_found")
    account = dict(row)
    if account.get("evaluation_activated_at"):
        raise ValueError("evaluation_already_activated")
    if account.get("plan") == "pro":
        raise ValueError("paid_account")
    conn.execute(
        "UPDATE accounts SET evaluation_type='enterprise', evaluation_status=COALESCE(evaluation_status,'ONBOARDING') WHERE account_id=?",
        (str(account_id),),
    )
    conn.commit()


def grant_evaluation_extension(conn, account_id, *, days, reason, real_usage,
                               insufficient_value_exposure, user_inactive=False, now=None):
    ensure_evaluation_schema(conn)
    try:
        days = int(days)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_extension_days") from exc
    if days <= 0:
        raise ValueError("invalid_extension_days")
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    if not row:
        raise ValueError("account_not_found")
    account = dict(row)
    if account.get("plan") == "pro" or account.get("evaluation_status") == "PAID":
        raise ValueError("paid_account")
    if not real_usage or not insufficient_value_exposure or user_inactive:
        raise ValueError("extension_not_eligible")
    current = int(account.get("evaluation_extension_days") or 0)
    if current + days > MAX_VALUE_EXTENSION_DAYS:
        raise ValueError("extension_limit_exceeded")
    ends = _parse_iso(account.get("evaluation_ends_at"))
    if not ends:
        raise ValueError("evaluation_not_activated")
    new_end = ends + timedelta(days=days)
    conn.execute(
        """UPDATE accounts SET evaluation_ends_at=?, evaluation_extension_days=?,
           evaluation_extension_reason=?, evaluation_status='EVALUATION_ACTIVE' WHERE account_id=?""",
        (new_end.isoformat(), current + days, str(reason or "").strip(), str(account_id)),
    )
    conn.commit()
    fresh = dict(conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone())
    return evaluation_summary(conn, fresh, now=_now(now))


def evaluation_access_state(account, *, now=None):
    """Return evaluation access state, or None for legacy/non-evaluation accounts."""
    if not account or not account.get("evaluation_status"):
        return None
    current = _now(now)
    status = account.get("evaluation_status")
    if status == "PAID":
        return None
    ends = _parse_iso(account.get("evaluation_ends_at"))
    if ends and ends <= current:
        return {
            "plan": "expired",
            "active": False,
            "source": "evaluation",
            "expires_at": account.get("evaluation_ends_at"),
            "evaluation_status": "EXPIRED",
        }
    if status == "CLOSED":
        return {"plan": "expired", "active": False, "source": "evaluation", "expires_at": ends.isoformat() if ends else None, "evaluation_status": "CLOSED"}
    return {
        "plan": "evaluation",
        "active": True,
        "source": "evaluation",
        "expires_at": account.get("evaluation_ends_at"),
        "evaluation_status": status,
    }


def mark_evaluation_paid(conn, account_id, *, occurred_at=None):
    ensure_evaluation_schema(conn)
    row = conn.execute("SELECT evaluation_status FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    if row and row[0] and row[0] != "PAID":
        when = _now(occurred_at)
        conn.execute("UPDATE accounts SET evaluation_status='PAID' WHERE account_id=?", (str(account_id),))
        _insert_event(conn, account_id, "paid_conversion", when)


def mark_post_conversion_churn(conn, account_id, *, occurred_at=None):
    ensure_evaluation_schema(conn)
    exists = conn.execute(
        "SELECT 1 FROM evaluation_events WHERE account_id=? AND event_name='paid_conversion' LIMIT 1",
        (str(account_id),),
    ).fetchone()
    if exists:
        _insert_event(conn, account_id, "post_conversion_churn", _now(occurred_at))


def _next_commercial_action(status, evaluation_type):
    if status == "PAID":
        return "RETAIN_AND_EXPAND"
    if status in {"EXPIRED", "CLOSED"}:
        return "CONVERT_TO_PRO"
    if status == "EVALUATION_ACTIVE":
        return "ASSISTED_PILOT_REVIEW" if evaluation_type == "enterprise" else "DEMONSTRATE_VALUE"
    return "COMPLETE_VALUE_ACTIVATION"


def evaluation_summary(conn, account, *, now=None):
    if not account or not account.get("evaluation_status"):
        return None
    current = _now(now)
    access = evaluation_access_state(account, now=current)
    status = "PAID" if account.get("evaluation_status") == "PAID" else (access or {}).get("evaluation_status", account.get("evaluation_status"))
    ends = _parse_iso(account.get("evaluation_ends_at"))
    remaining = None
    if ends and status != "PAID":
        remaining = max(0, math.ceil((ends - current).total_seconds() / 86400))
    events = _event_names(conn, account.get("account_id"))
    evaluation_type = account.get("evaluation_type") or "legacy"
    return {
        "type": evaluation_type,
        "status": status,
        "activated_at": account.get("evaluation_activated_at"),
        "ends_at": account.get("evaluation_ends_at"),
        "days_remaining": remaining,
        "extension_days": int(account.get("evaluation_extension_days") or 0),
        "extension_reason": account.get("evaluation_extension_reason"),
        "value_status": account.get("evaluation_value_status") or "UNKNOWN",
        "activation_reason": account.get("evaluation_activation_reason"),
        "next_commercial_action": _next_commercial_action(status, evaluation_type),
        "activation_requirements": {
            "profile_ready": "profile_ready" in events,
            "market_data_available": "market_data_available" in events,
            "first_relevant_shortlist_generated": "first_shortlist_generated" in events,
        },
    }


def evaluation_metrics(conn, account, *, now=None):
    if not account or not account.get("evaluation_status"):
        return None
    rows = conn.execute(
        "SELECT event_name, occurred_at FROM evaluation_events WHERE account_id=? ORDER BY occurred_at",
        (str(account.get("account_id")),),
    ).fetchall()
    events = [(row[0], _parse_iso(row[1])) for row in rows]
    created = _parse_iso(account.get("created_at"))
    activated = _parse_iso(account.get("evaluation_activated_at"))

    first_exposure = next((ts for name, ts in events if name in VALUE_EXPOSURE_EVENTS and ts), None)
    value_available = next((ts for name, ts in events if name == "first_shortlist_generated" and ts), None)
    first_observed = next((ts for name, ts in events if name in ENGAGEMENT_EVENTS and ts), None)
    names = [name for name, _ in events]
    exposure_count = sum(1 for name in names if name in VALUE_EXPOSURE_EVENTS)
    engagement_count = sum(1 for name in names if name in ENGAGEMENT_EVENTS)

    def active_on_day(day):
        if not activated:
            return False
        floor = activated + timedelta(days=day)
        ceiling = floor + timedelta(days=1)
        # Product-generated availability or delivery alone is not customer activity.
        return any(ts and floor <= ts < ceiling and name in ENGAGEMENT_EVENTS for name, ts in events)

    exposure_seconds = int((first_exposure - created).total_seconds()) if first_exposure and created else None
    available_seconds = int((value_available - created).total_seconds()) if value_available and created else None
    observed_seconds = int((first_observed - created).total_seconds()) if first_observed and created else None

    return {
        # Availability, observed engagement, and verified customer value are
        # deliberately different truths. The product can observe interaction;
        # it still has no canonical evidence-backed verified-value event.
        "TIME_TO_VALUE_AVAILABLE_SECONDS": available_seconds,
        "TIME_TO_OBSERVED_FIRST_VALUE_SECONDS": observed_seconds,
        "TIME_TO_FIRST_VALUE_EXPOSURE_SECONDS": exposure_seconds,
        "TIME_TO_FIRST_VALUE_SECONDS": None,
        "TIME_TO_FIRST_VERIFIED_VALUE_SECONDS": None,
        "FIRST_VERIFIED_VALUE_RECORDED": False,
        "first_value_semantics": "NO_CANONICAL_VERIFIED_VALUE_EVENT",
        "TIME_TO_FIRST_REPEAT_VALUE_SECONDS": None,
        "REPEAT_VALUE_RECORDED": False,
        "repeat_value_semantics": "REQUIRES_CANONICAL_VERIFIED_VALUE_AND_NEW_VALUE_EVENT",
        "TRIAL_ACTIVATION_RATE": 1 if activated else 0,
        "VALUE_EXPOSURE_RATE": 1 if exposure_count else 0,
        "DAY_1_ACTIVE": active_on_day(1),
        "DAY_7_ACTIVE": active_on_day(7),
        "DAY_14_ACTIVE": active_on_day(14),
        "DAY_21_ACTIVE": active_on_day(21),
        "TRIAL_TO_PAID": 1 if "paid_conversion" in names else 0,
        "EXTENSION_RATE": 1 if int(account.get("evaluation_extension_days") or 0) > 0 else 0,
        "EXTENSION_TO_PAID": 1 if int(account.get("evaluation_extension_days") or 0) > 0 and "paid_conversion" in names else 0,
        "CHURN_AFTER_CONVERSION": 1 if "post_conversion_churn" in names else 0,
        "exposure_event_count": exposure_count,
        "engagement_event_count": engagement_count,
        "measured_value_event_count": 0,
        "estimated_value_event_count": 0,
    }
