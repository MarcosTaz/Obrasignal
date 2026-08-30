"""Decision-useful measurement truth for ObraSignal.

This module is intentionally read-only. It does not create analytics storage, mutate
product/domain state, or reinterpret another owner's source of truth. Its purpose is
to make the current measurement boundary explicit so missing instrumentation cannot
silently become a zero, a funnel conversion, or a causal conclusion.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

SCHEMA_VERSION = "measurement-truth-v1"

OBSERVABLE = "OBSERVABLE"
PARTIAL = "PARTIAL"
MISSING = "MISSING"
UNKNOWN = "UNKNOWN"

# `source_kind` is intentionally explicit. In particular, opportunity_decisions is
# a SYSTEM/DOMAIN classification log and must never be presented as a customer
# go/no-go action merely because the word "decision" appears in its schema.
_EVENT_TAXONOMY = {
    "signup": {
        "status": PARTIAL,
        "source_kind": "ACCOUNT_LIFECYCLE",
        "source": "accounts.created_at",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "account row creation time; not proven equivalent to completed signup UX",
        "dedupe": "accounts.account_id primary key",
        "missing_behavior": "UNKNOWN; missing account row is not zero signups",
    },
    "profile_completion": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_LIFECYCLE",
        "source": "evaluation_events.profile_ready + company_profiles.updated_at",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "profile_ready is event time when telemetry succeeds; company_profiles.updated_at is latest durable write, not first completion",
        "dedupe": "evaluation_events UNIQUE(account_id,event_name,occurred_at); profile row keyed by account_id",
        "missing_behavior": "profile row without profile_ready means telemetry history is incomplete, not that completion did not happen",
    },
    "market_readiness": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_LIFECYCLE",
        "source": "evaluation_events.market_data_available",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "event occurrence when explicitly recorded",
        "dedupe": "evaluation_events UNIQUE(account_id,event_name,occurred_at)",
        "missing_behavior": "UNKNOWN while real customer-path wiring is incomplete (GAP-GP-013)",
    },
    "first_shortlist": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_VALUE",
        "source": "evaluation_events.first_shortlist_generated",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "event occurrence when explicitly recorded",
        "dedupe": "evaluation_events UNIQUE(account_id,event_name,occurred_at)",
        "missing_behavior": "UNKNOWN while real shortlist wiring is incomplete (GAP-GP-013)",
    },
    "opportunity_viewed": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_ACTION",
        "source": "evaluation_events.relevant_opportunity_viewed",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "event occurrence only if explicitly recorded",
        "dedupe": "evaluation_events UNIQUE(account_id,event_name,occurred_at)",
        "missing_behavior": "UNKNOWN; current detail renderer does not itself prove view instrumentation",
    },
    "evidence_viewed": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_ACTION",
        "source": "evaluation_events.evidence_viewed",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "event occurrence only if explicitly recorded",
        "dedupe": "evaluation_events UNIQUE(account_id,event_name,occurred_at)",
        "missing_behavior": "UNKNOWN; absence is not a zero-view claim",
    },
    "customer_decision": {
        "status": MISSING,
        "source_kind": "CUSTOMER_ACTION",
        "source": None,
        "tenant_boundary": "required: account_id",
        "timestamp_semantics": "not currently proven",
        "dedupe": "not currently proven",
        "missing_behavior": "UNKNOWN; opportunity_decisions is system/domain classification, not customer action",
    },
    "save_watch": {
        "status": MISSING,
        "source_kind": "CUSTOMER_ACTION",
        "source": None,
        "tenant_boundary": "required: account_id",
        "timestamp_semantics": "not currently proven",
        "dedupe": "not currently proven",
        "missing_behavior": "UNKNOWN; unmerged watchlist work is not canonical measurement truth",
    },
    "workflow_action": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_WORKFLOW",
        "source": "opportunity_workflow.status + updated_at",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "latest state update only; prior transitions are overwritten",
        "dedupe": "UNIQUE(account_id,source,external_id) current-state row",
        "missing_behavior": "UNKNOWN for transition count/order/duration; current row is not an event history",
    },
    "alert": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_NOTIFICATION",
        "source": "opportunity_events.created_at + delivered_at",
        "tenant_boundary": "account_id embedded in event_key and stored on row",
        "timestamp_semantics": "created_at proves alert candidate creation; delivery/closed-app return remain separate claims",
        "dedupe": "globally unique event_key containing account identity",
        "missing_behavior": "UNKNOWN for actual delivery/return while server delivery journey is incomplete",
    },
    "return": {
        "status": MISSING,
        "source_kind": "CUSTOMER_ACTION",
        "source": None,
        "tenant_boundary": "required: account_id",
        "timestamp_semantics": "not currently proven",
        "dedupe": "not currently proven",
        "missing_behavior": "UNKNOWN; request traffic is not silently redefined as meaningful customer return",
    },
    "evaluation_activation": {
        "status": PARTIAL,
        "source_kind": "COMMERCIAL_LIFECYCLE",
        "source": "accounts.evaluation_activated_at + evaluation_events",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "activation timestamp is set when all required lifecycle events have been recorded",
        "dedupe": "account lifecycle state plus event constraints",
        "missing_behavior": "UNKNOWN when upstream activation event wiring is incomplete",
    },
    "billing_state": {
        "status": PARTIAL,
        "source_kind": "COMMERCIAL_LIFECYCLE",
        "source": "accounts.plan/subscription_status/billing_synced_at + billing_webhook_events",
        "tenant_boundary": "account_id on account state; webhook dedupe is event_id",
        "timestamp_semantics": "current account snapshot plus webhook receipt time; not a complete billing-state transition ledger",
        "dedupe": "accounts.account_id primary key; billing_webhook_events.event_id",
        "missing_behavior": "UNKNOWN for unobserved/failed verification; never infer Evaluation or paid state from missing verification",
    },
    "conversion": {
        "status": OBSERVABLE,
        "source_kind": "COMMERCIAL_LIFECYCLE",
        "source": "evaluation_events.paid_conversion",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "server lifecycle records paid_conversion when authoritative account state becomes paid",
        "dedupe": "evaluation_events UNIQUE(account_id,event_name,occurred_at)",
        "missing_behavior": "no event is not sufficient evidence of a population conversion rate without a defined eligible denominator",
    },
    "outcome": {
        "status": PARTIAL,
        "source_kind": "CUSTOMER_OUTCOME",
        "source": "opportunity_workflow current WON/LOST state only",
        "tenant_boundary": "account_id",
        "timestamp_semantics": "latest workflow update time; not a durable outcome-event history",
        "dedupe": "UNIQUE(account_id,source,external_id) current-state row",
        "missing_behavior": "UNKNOWN for outcome history/quality unless the Outcome owner supplies canonical evidence",
    },
}

_REQUIRED_CONTRACT_FIELDS = frozenset({
    "status",
    "source_kind",
    "source",
    "tenant_boundary",
    "timestamp_semantics",
    "dedupe",
    "missing_behavior",
})


def event_taxonomy():
    """Return a copy of the canonical measurement registry."""
    return deepcopy(_EVENT_TAXONOMY)


def validate_event_taxonomy():
    """Fail closed if an event contract omits a data-quality boundary."""
    failures = {}
    for name, contract in _EVENT_TAXONOMY.items():
        missing = sorted(_REQUIRED_CONTRACT_FIELDS - set(contract))
        if missing:
            failures[name] = missing
    if failures:
        raise ValueError({"invalid_measurement_contract": failures})
    return True


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _columns(conn, table):
    if not _table_exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return row


def _first_event(conn, account_id, event_name):
    if not _table_exists(conn, "evaluation_events"):
        return None
    row = conn.execute(
        "SELECT occurred_at FROM evaluation_events WHERE account_id=? AND event_name=? ORDER BY occurred_at,id LIMIT 1",
        (str(account_id), event_name),
    ).fetchone()
    return row[0] if row else None


def account_milestones(conn, account_id):
    """Read customer milestones without manufacturing events from snapshots.

    Each milestone has a `quality` field. `UNKNOWN` means the system cannot safely
    determine the event from current durable evidence; it never means zero.
    """
    account_id = str(account_id)
    account = None
    if _table_exists(conn, "accounts"):
        cols = _columns(conn, "accounts")
        wanted = [name for name in ("account_id", "created_at", "evaluation_activated_at") if name in cols]
        if wanted:
            account = _one(
                conn,
                f"SELECT {','.join(wanted)} FROM accounts WHERE account_id=?",
                (account_id,),
            )
            if account is not None and not isinstance(account, dict):
                account = dict(zip(wanted, account))

    signup_at = account.get("created_at") if isinstance(account, dict) else None
    activated_at = account.get("evaluation_activated_at") if isinstance(account, dict) else None

    profile_event = _first_event(conn, account_id, "profile_ready")
    profile_latest = None
    if _table_exists(conn, "company_profiles") and "updated_at" in _columns(conn, "company_profiles"):
        row = conn.execute(
            "SELECT updated_at FROM company_profiles WHERE account_id=?", (account_id,)
        ).fetchone()
        profile_latest = row[0] if row else None

    def event_milestone(event_name):
        occurred = _first_event(conn, account_id, event_name)
        return {
            "quality": OBSERVABLE if occurred else UNKNOWN,
            "occurred_at": occurred,
            "reason": None if occurred else "event_not_observed; missing instrumentation is not zero",
        }

    profile = {
        "quality": OBSERVABLE if profile_event else (PARTIAL if profile_latest else UNKNOWN),
        "occurred_at": profile_event,
        "latest_persisted_at": profile_latest,
        "reason": (
            None
            if profile_event
            else (
                "durable profile exists but first completion event is not proven"
                if profile_latest
                else "profile completion is not observed"
            )
        ),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "account_id": account_id,
        "signup": {
            "quality": PARTIAL if signup_at else UNKNOWN,
            "occurred_at": signup_at,
            "reason": (
                "account row creation time; signup UX completion semantics are not proven"
                if signup_at
                else "account creation is not observed"
            ),
        },
        "profile_completion": profile,
        "market_readiness": event_milestone("market_data_available"),
        "first_shortlist": event_milestone("first_shortlist_generated"),
        "opportunity_viewed": event_milestone("relevant_opportunity_viewed"),
        "evidence_viewed": event_milestone("evidence_viewed"),
        "evaluation_activation": {
            "quality": OBSERVABLE if activated_at else UNKNOWN,
            "occurred_at": activated_at,
            "reason": None if activated_at else "evaluation activation is not observed",
        },
        "conversion": event_milestone("paid_conversion"),
    }


def duration_seconds(start, end):
    """Return a duration only when both timestamps are valid and ordered."""
    if not start or not end:
        return {"quality": UNKNOWN, "seconds": None, "reason": "missing_endpoint"}
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return {"quality": UNKNOWN, "seconds": None, "reason": "invalid_timestamp"}
    seconds = int((end_dt.astimezone(timezone.utc) - start_dt.astimezone(timezone.utc)).total_seconds())
    if seconds < 0:
        return {"quality": UNKNOWN, "seconds": None, "reason": "end_before_start"}
    return {"quality": OBSERVABLE, "seconds": seconds, "reason": None}


def instrumentation_debt():
    """Decision-changing gaps only; ordered by near-term customer/commercial value."""
    return [
        {
            "priority": "P0",
            "gap": "activation_event_wiring",
            "events": ["market_readiness", "first_shortlist"],
            "decision_blocked": "where customers drop before Evaluation activation and true time-to-value",
            "owner_boundary": "Evaluation/Profile/Radar integration (GAP-GP-013)",
        },
        {
            "priority": "P0",
            "gap": "customer_action_events",
            "events": ["opportunity_viewed", "evidence_viewed", "customer_decision"],
            "decision_blocked": "which product surfaces create useful decisions and repeat value",
            "owner_boundary": "Analytics contract + Web/Decision public instrumentation points",
        },
        {
            "priority": "P1",
            "gap": "workflow_transition_history",
            "events": ["workflow_action", "outcome"],
            "decision_blocked": "workflow continuity, time between actions, and outcome progression",
            "owner_boundary": "Workflow/Outcome persistence owner; Analytics consumes public event contract",
        },
        {
            "priority": "P1",
            "gap": "notification_delivery_return",
            "events": ["alert", "return"],
            "decision_blocked": "whether alerts drive reliable customer return",
            "owner_boundary": "Notification delivery (#57/#263); Analytics consumes delivery/return evidence",
        },
    ]
