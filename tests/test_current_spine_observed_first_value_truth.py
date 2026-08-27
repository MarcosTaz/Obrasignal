"""Current-spine failing-before for observed customer First Value truth.

Generated availability and delivery evidence are useful facts, but neither proves
customer-observed value. Real relevant interaction must remain a separate clock.
"""
from datetime import datetime, timezone
import sqlite3
from pathlib import Path

from account_registry import ensure_account
from evaluation_policy import evaluation_metrics, record_evaluation_event


ROOT = Path(__file__).resolve().parents[1]
API_TEXT = (ROOT / "api.py").read_text(encoding="utf-8")


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    conn.execute(
        """UPDATE accounts SET created_at=?, evaluation_status='EVALUATION_ACTIVE',
           evaluation_type='standard' WHERE account_id='tenant-a'""",
        ("2026-08-27T10:00:00+00:00",),
    )
    conn.commit()
    return conn


def _account(conn):
    return dict(conn.execute("SELECT * FROM accounts WHERE account_id='tenant-a'").fetchone())


def test_generated_shortlist_is_available_not_observed_first_value():
    conn = _conn()
    record_evaluation_event(
        conn,
        "tenant-a",
        "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 27, 10, 5, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None, (
        "FALSE_FIRST_VALUE: product-generated shortlist availability became customer-observed First Value"
    )


def test_alert_delivery_is_delivery_evidence_not_observed_first_value():
    conn = _conn()
    record_evaluation_event(
        conn,
        "tenant-a",
        "alert_delivered",
        occurred_at=datetime(2026, 8, 27, 10, 6, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None, (
        "FALSE_FIRST_VALUE: alert delivery evidence became customer-observed First Value"
    )


def test_real_relevant_view_can_establish_observed_first_value_clock():
    conn = _conn()
    record_evaluation_event(
        conn,
        "tenant-a",
        "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 27, 10, 5, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    record_evaluation_event(
        conn,
        "tenant-a",
        "relevant_opportunity_viewed",
        occurred_at=datetime(2026, 8, 27, 10, 7, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] == 420


def test_current_customer_routes_have_observed_value_evidence_hooks():
    # Current customer routes must be capable of creating bounded observed evidence;
    # metric repair alone is insufficient if no real interaction can populate it.
    assert "relevant_opportunity_viewed" in API_TEXT, (
        "FIRST_VALUE_OBSERVATION_PATH_MISSING: current opportunity detail route emits no observed-value evidence"
    )
    assert "action_taken" in API_TEXT, (
        "CUSTOMER_ACTION_OBSERVATION_PATH_MISSING: current workflow route emits no material-action evidence"
    )
