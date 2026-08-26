import json
import sqlite3

from account_registry import ensure_account
from customer_value_read_model import customer_value_summary
from evaluation_policy import ensure_evaluation_schema


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    ensure_account(conn, "tenant-b")
    ensure_evaluation_schema(conn)
    conn.execute(
        "UPDATE accounts SET created_at='2026-08-26T10:00:00+00:00' WHERE account_id IN ('tenant-a','tenant-b')"
    )
    conn.commit()
    return conn


def _event(conn, account, name, at, metadata=None):
    conn.execute(
        "INSERT INTO evaluation_events(account_id,event_name,occurred_at,metadata_json) VALUES(?,?,?,?)",
        (account, name, at, json.dumps(metadata or {}, separators=(",", ":"))),
    )
    conn.commit()


def test_no_evidence_remains_unproven():
    conn = _conn()
    summary = customer_value_summary(conn, "tenant-a")
    assert summary["state"] == "UNPROVEN"
    assert summary["value_available"] is False
    assert summary["first_value_observed"] is False
    assert summary["repeat_value_observed"] is False


def test_generated_relevant_shortlist_is_value_available_not_observed_first_value():
    conn = _conn()
    _event(
        conn,
        "tenant-a",
        "first_shortlist_generated",
        "2026-08-26T10:05:00+00:00",
        {"source": "TED", "external_id": "N-1", "relevance_state": "RELEVANT"},
    )

    summary = customer_value_summary(conn, "tenant-a")
    assert summary["state"] == "VALUE_AVAILABLE"
    assert summary["value_available"] is True
    assert summary["first_value_observed"] is False
    assert summary["time_to_value_available_seconds"] == 300
    assert summary["time_to_observed_first_value_seconds"] is None


def test_alert_delivery_is_delivery_evidence_not_customer_observation():
    conn = _conn()
    _event(conn, "tenant-a", "first_shortlist_generated", "2026-08-26T10:05:00+00:00")
    _event(
        conn,
        "tenant-a",
        "alert_delivered",
        "2026-08-26T10:06:00+00:00",
        {"source": "TED", "external_id": "N-1"},
    )

    summary = customer_value_summary(conn, "tenant-a")
    assert summary["state"] == "VALUE_AVAILABLE"
    assert summary["delivery_evidence_count"] == 1
    assert summary["observed_interaction_count"] == 0
    assert summary["first_value_observed"] is False


def test_relevant_opportunity_view_is_observed_first_value():
    conn = _conn()
    _event(conn, "tenant-a", "first_shortlist_generated", "2026-08-26T10:05:00+00:00")
    _event(
        conn,
        "tenant-a",
        "relevant_opportunity_viewed",
        "2026-08-26T10:07:00+00:00",
        {"source": "TED", "external_id": "N-1"},
    )

    summary = customer_value_summary(conn, "tenant-a")
    assert summary["state"] == "FIRST_VALUE_OBSERVED"
    assert summary["first_value_observed"] is True
    assert summary["repeat_value_observed"] is False
    assert summary["time_to_observed_first_value_seconds"] == 420
    assert summary["ordering"] == "CONSISTENT"


def test_same_route_retry_inside_five_minute_bucket_does_not_inflate_repeat_value():
    conn = _conn()
    _event(conn, "tenant-a", "first_shortlist_generated", "2026-08-26T10:05:00+00:00")
    metadata = {"source": "TED", "external_id": "N-1"}
    _event(conn, "tenant-a", "relevant_opportunity_viewed", "2026-08-26T10:07:01+00:00", metadata)
    _event(conn, "tenant-a", "relevant_opportunity_viewed", "2026-08-26T10:07:40+00:00", metadata)

    summary = customer_value_summary(conn, "tenant-a")
    assert summary["observed_interaction_count"] == 1
    assert summary["state"] == "FIRST_VALUE_OBSERVED"
    assert summary["repeat_value_observed"] is False


def test_later_revisit_or_distinct_customer_action_can_prove_repeat_value():
    conn = _conn()
    _event(conn, "tenant-a", "first_shortlist_generated", "2026-08-26T10:05:00+00:00")
    _event(
        conn,
        "tenant-a",
        "relevant_opportunity_viewed",
        "2026-08-26T10:07:00+00:00",
        {"source": "TED", "external_id": "N-1"},
    )
    _event(
        conn,
        "tenant-a",
        "action_taken",
        "2026-08-26T10:08:00+00:00",
        {"source": "TED", "external_id": "N-1", "from_status": "NEW", "to_status": "REVIEWING"},
    )

    summary = customer_value_summary(conn, "tenant-a")
    assert summary["observed_interaction_count"] == 2
    assert summary["state"] == "REPEAT_VALUE_OBSERVED"
    assert summary["repeat_value_observed"] is True
    assert summary["repeat_value_observed_at"] == "2026-08-26T10:08:00+00:00"


def test_customer_value_read_model_is_tenant_isolated():
    conn = _conn()
    _event(conn, "tenant-a", "first_shortlist_generated", "2026-08-26T10:05:00+00:00")
    _event(
        conn,
        "tenant-a",
        "relevant_opportunity_viewed",
        "2026-08-26T10:07:00+00:00",
        {"source": "TED", "external_id": "N-1"},
    )

    assert customer_value_summary(conn, "tenant-a")["state"] == "FIRST_VALUE_OBSERVED"
    assert customer_value_summary(conn, "tenant-b")["state"] == "UNPROVEN"


def test_observed_event_without_available_evidence_is_exposed_as_ordering_gap_not_clean_chain():
    conn = _conn()
    _event(
        conn,
        "tenant-a",
        "action_taken",
        "2026-08-26T10:08:00+00:00",
        {"source": "TED", "external_id": "N-1", "to_status": "REVIEWING"},
    )

    summary = customer_value_summary(conn, "tenant-a")
    assert summary["state"] == "FIRST_VALUE_OBSERVED"
    assert summary["value_available"] is False
    assert summary["ordering"] == "AVAILABLE_EVIDENCE_MISSING"
    assert summary["commercial_outcome"] == "UNPROVEN"
