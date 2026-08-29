import sqlite3
from datetime import datetime, timedelta, timezone

from account_registry import ensure_account, get_account
from evaluation_policy import evaluation_metrics, record_evaluation_event


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_generated_availability_is_not_observed_or_verified_value():
    conn = _db()
    account_id = "tenant-a"
    ensure_account(conn, account_id)
    created = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    conn.execute("UPDATE accounts SET created_at=? WHERE account_id=?", (created.isoformat(), account_id))
    conn.commit()
    record_evaluation_event(conn, account_id, "profile_ready", occurred_at=created + timedelta(seconds=1))
    record_evaluation_event(conn, account_id, "market_data_available", occurred_at=created + timedelta(seconds=2))
    record_evaluation_event(conn, account_id, "first_shortlist_generated", occurred_at=created + timedelta(seconds=3))

    metrics = evaluation_metrics(conn, get_account(conn, account_id), now=created + timedelta(seconds=10))
    assert metrics["TIME_TO_VALUE_AVAILABLE_SECONDS"] == 3
    assert metrics["TIME_TO_OBSERVED_FIRST_VALUE_SECONDS"] is None
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
    assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False


def test_real_engagement_gets_observed_clock_but_not_verified_value():
    conn = _db()
    account_id = "tenant-a"
    ensure_account(conn, account_id)
    created = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    conn.execute("UPDATE accounts SET created_at=? WHERE account_id=?", (created.isoformat(), account_id))
    conn.commit()
    record_evaluation_event(conn, account_id, "profile_ready", occurred_at=created + timedelta(seconds=1))
    record_evaluation_event(conn, account_id, "market_data_available", occurred_at=created + timedelta(seconds=2))
    record_evaluation_event(conn, account_id, "first_shortlist_generated", occurred_at=created + timedelta(seconds=3))
    record_evaluation_event(conn, account_id, "relevant_opportunity_viewed", occurred_at=created + timedelta(seconds=7))

    metrics = evaluation_metrics(conn, get_account(conn, account_id), now=created + timedelta(seconds=10))
    assert metrics["TIME_TO_VALUE_AVAILABLE_SECONDS"] == 3
    assert metrics["TIME_TO_OBSERVED_FIRST_VALUE_SECONDS"] == 7
    assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
    assert metrics["TIME_TO_FIRST_VERIFIED_VALUE_SECONDS"] is None
    assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False
