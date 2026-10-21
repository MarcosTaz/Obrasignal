import sqlite3
from datetime import datetime, timezone


def test_evaluation_invalid_end_is_detected():
    from account_registry import ensure_account
    from data_integrity_evaluation import scan_evaluation_time_integrity
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
    state = evaluation_access_state(account, now=datetime(2026, 8, 25, tzinfo=timezone.utc))
    assert state["active"] is True

    findings = scan_evaluation_time_integrity(conn, exact_sha="66d43f6f")
    assert [f.invariant for f in findings] == ["EVALUATION_ACTIVE_WINDOW_CORRUPT"]
    assert findings[0].severity == "HIGH"
    assert findings[0].owner == "Evaluation"
    conn.close()


def test_evaluation_event_naive_timestamp_is_detected_read_only():
    from account_registry import ensure_account
    from data_integrity_evaluation import scan_evaluation_time_integrity
    from evaluation_policy import ensure_evaluation_schema

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    ensure_evaluation_schema(conn)
    conn.execute(
        "INSERT INTO evaluation_events(account_id,event_name,occurred_at,metadata_json) VALUES(?,?,?,?)",
        ("tenant-a", "profile_ready", "2026-08-25 10:00:00", "{}"),
    )
    conn.commit()
    before = conn.total_changes
    conn.execute("PRAGMA query_only=ON")

    findings = scan_evaluation_time_integrity(conn)
    assert [f.invariant for f in findings] == ["EVALUATION_EVENT_TIMESTAMP_CORRUPT"]
    assert conn.total_changes == before
    conn.close()
