from datetime import datetime, timezone
import sqlite3

from account_registry import ensure_account
from evaluation_policy import evaluation_metrics, record_evaluation_event


def _conn(*, activated_at=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    conn.execute(
        """UPDATE accounts SET created_at=?, evaluation_status='EVALUATION_ACTIVE',
           evaluation_type='standard', evaluation_activated_at=? WHERE account_id='tenant-a'""",
        ("2026-08-26T10:00:00+00:00", activated_at),
    )
    conn.commit()
    return conn


def _account(conn):
    return dict(conn.execute("SELECT * FROM accounts WHERE account_id='tenant-a'").fetchone())


def test_generated_shortlist_sets_available_clock_not_observed_first_value():
    conn = _conn()
    record_evaluation_event(
        conn, "tenant-a", "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 26, 10, 5, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_VALUE_AVAILABLE_SECONDS"] == 300
    assert metrics["TIME_TO_OBSERVED_FIRST_VALUE_SECONDS"] is None
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
    assert metrics["VALUE_EXPOSURE_RATE"] == 1


def test_alert_delivery_is_exposure_not_observed_first_value():
    conn = _conn()
    record_evaluation_event(
        conn, "tenant-a", "alert_delivered",
        occurred_at=datetime(2026, 8, 26, 10, 6, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_VALUE_AVAILABLE_SECONDS"] is None
    assert metrics["TIME_TO_OBSERVED_FIRST_VALUE_SECONDS"] is None
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
    assert metrics["VALUE_EXPOSURE_RATE"] == 1


def test_relevant_view_establishes_observed_clock_without_replacing_available_clock():
    conn = _conn()
    record_evaluation_event(
        conn, "tenant-a", "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 26, 10, 5, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    record_evaluation_event(
        conn, "tenant-a", "relevant_opportunity_viewed",
        occurred_at=datetime(2026, 8, 26, 10, 7, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["TIME_TO_VALUE_AVAILABLE_SECONDS"] == 300
    assert metrics["TIME_TO_OBSERVED_FIRST_VALUE_SECONDS"] == 420
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] == 420


def test_generated_or_delivered_events_do_not_fabricate_day_active():
    conn = _conn(activated_at="2026-08-26T10:00:00+00:00")
    record_evaluation_event(
        conn, "tenant-a", "first_shortlist_generated",
        occurred_at=datetime(2026, 8, 27, 10, 5, tzinfo=timezone.utc),
    )
    record_evaluation_event(
        conn, "tenant-a", "alert_delivered",
        occurred_at=datetime(2026, 9, 2, 10, 5, tzinfo=timezone.utc),
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["DAY_1_ACTIVE"] is False
    assert metrics["DAY_7_ACTIVE"] is False


def test_real_engagement_can_establish_day_active():
    conn = _conn(activated_at="2026-08-26T10:00:00+00:00")
    record_evaluation_event(
        conn, "tenant-a", "relevant_opportunity_viewed",
        occurred_at=datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc),
        metadata={"source": "TED", "external_id": "N-1"},
    )
    metrics = evaluation_metrics(conn, _account(conn))
    assert metrics["DAY_1_ACTIVE"] is True
    assert metrics["engagement_event_count"] == 1
