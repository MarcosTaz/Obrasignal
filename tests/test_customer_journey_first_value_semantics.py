import sqlite3
from datetime import datetime, timedelta, timezone


def test_value_exposure_is_not_reported_as_verified_first_value():
    from account_registry import ensure_account, get_account
    from evaluation_policy import evaluation_metrics, record_evaluation_event

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        ensure_account(conn, "company-value-semantics")
        created = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        conn.execute(
            "UPDATE accounts SET created_at=? WHERE account_id=?",
            (created.isoformat(), "company-value-semantics"),
        )
        conn.commit()

        record_evaluation_event(
            conn,
            "company-value-semantics",
            "profile_ready",
            occurred_at=created + timedelta(seconds=1),
        )
        record_evaluation_event(
            conn,
            "company-value-semantics",
            "market_data_available",
            occurred_at=created + timedelta(seconds=2),
        )
        record_evaluation_event(
            conn,
            "company-value-semantics",
            "first_shortlist_generated",
            occurred_at=created + timedelta(seconds=3),
        )
        record_evaluation_event(
            conn,
            "company-value-semantics",
            "relevant_opportunity_viewed",
            occurred_at=created + timedelta(seconds=4),
        )
        record_evaluation_event(
            conn,
            "company-value-semantics",
            "action_taken",
            occurred_at=created + timedelta(seconds=5),
        )

        metrics = evaluation_metrics(conn, get_account(conn, "company-value-semantics"), now=created + timedelta(seconds=10))

        assert metrics["VALUE_EXPOSURE_RATE"] == 1
        assert metrics["TIME_TO_FIRST_VALUE_EXPOSURE_SECONDS"] == 3
        assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
        assert metrics["TIME_TO_FIRST_VERIFIED_VALUE_SECONDS"] is None
        assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False
        assert metrics["first_value_semantics"] == "NO_CANONICAL_VERIFIED_VALUE_EVENT"
    finally:
        conn.close()


def test_action_taken_does_not_become_verified_value():
    from account_registry import ensure_account, get_account
    from evaluation_policy import evaluation_metrics, record_evaluation_event

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        ensure_account(conn, "company-action-only")
        now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        record_evaluation_event(conn, "company-action-only", "action_taken", occurred_at=now)
        metrics = evaluation_metrics(conn, get_account(conn, "company-action-only"), now=now)
        assert metrics["engagement_event_count"] == 1
        assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False
        assert metrics["TIME_TO_FIRST_VERIFIED_VALUE_SECONDS"] is None
    finally:
        conn.close()
