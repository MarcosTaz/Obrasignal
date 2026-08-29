"""Current-trust probes for corrupt temporal data truth."""
import sqlite3
from datetime import datetime, timezone


def test_malformed_source_success_timestamp_cannot_remain_healthy():
    from source_health import ensure_source_health, source_health_snapshot

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    conn.execute(
        """INSERT INTO source_health
           (source,last_attempt,last_success,last_error,last_duration_ms,last_found,last_new_items,status)
           VALUES(?,?,?,?,?,?,?,?)""",
        ("TED", "2026-08-27T12:00:00+00:00", "not-a-time", None, 10, 1, 1, "healthy"),
    )
    conn.commit()
    snapshot = source_health_snapshot(conn)
    assert snapshot
    assert snapshot[0]["status"] != "healthy"
    assert snapshot[0]["age_minutes"] is None
    conn.close()


def test_malformed_evaluation_end_cannot_preserve_active_access():
    from account_registry import ensure_account
    from evaluation_policy import ensure_evaluation_schema, evaluation_access_state

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    ensure_evaluation_schema(conn)
    conn.execute(
        "UPDATE accounts SET evaluation_status=?, evaluation_activated_at=?, evaluation_ends_at=? WHERE account_id=?",
        ("EVALUATION_ACTIVE", "2026-08-01T00:00:00+00:00", "not-a-time", "tenant-a"),
    )
    conn.commit()
    account = dict(conn.execute("SELECT * FROM accounts WHERE account_id=?", ("tenant-a",)).fetchone())
    state = evaluation_access_state(account, now=datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert state["active"] is False
    conn.close()
