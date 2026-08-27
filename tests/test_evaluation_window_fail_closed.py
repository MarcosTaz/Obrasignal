from datetime import datetime, timezone
import sqlite3

from account_registry import ensure_account
from evaluation_policy import ensure_evaluation_schema, evaluation_access_state


def test_malformed_evaluation_end_is_not_active():
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
    assert state["evaluation_status"] == "UNKNOWN"
    conn.close()
