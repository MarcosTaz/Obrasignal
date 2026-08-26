"""Failing-before probe for observed First Value metric semantics.

Generated availability and delivery evidence must not be coerced into customer-
observed First Value. Preserve this probe as diagnostic evidence only.
"""
from datetime import datetime, timezone
import sqlite3

from account_registry import ensure_account
from evaluation_policy import evaluation_metrics, record_evaluation_event


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    conn.execute(
        """UPDATE accounts SET created_at=?, evaluation_status='EVALUATION_ACTIVE',
           evaluation_type='standard' WHERE account_id='tenant-a'""",
        ("2026-08-26T10:00:00+00:00",),
    )
    conn.commit()
    return conn


def _account(conn):
    return dict(conn.execute("SELECT * FROM accounts WHERE account_id='tenant-a'").fetchone())


def test_generated_shortlist_is_not_time_to_observed_first_value():
    conn = _conn()
    record_evaluation_event(
        conn,
        "tenant-a",
        "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 26, 10, 5, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )

    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None


def test_alert_delivery_is_not_time_to_observed_first_value():
    conn = _conn()
    record_evaluation_event(
        conn,
        "tenant-a",
        "alert_delivered",
        occurred_at=datetime(2026, 8, 26, 10, 6, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )

    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None


def test_real_relevant_view_can_establish_observed_first_value_clock():
    conn = _conn()
    record_evaluation_event(
        conn,
        "tenant-a",
        "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 26, 10, 5, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    record_evaluation_event(
        conn,
        "tenant-a",
        "relevant_opportunity_viewed",
        occurred_at=datetime(2026, 8, 26, 10, 7, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )

    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] == 420
