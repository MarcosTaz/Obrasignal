from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from account_registry import ensure_account
from evaluation_policy import ensure_evaluation_schema, evaluation_access_state, grant_evaluation_extension


def _account(activated_at, ends_at):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    ensure_evaluation_schema(conn)
    conn.execute(
        "UPDATE accounts SET evaluation_status=?, evaluation_activated_at=?, evaluation_ends_at=? WHERE account_id=?",
        ("EVALUATION_ACTIVE", activated_at, ends_at, "tenant-a"),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM accounts WHERE account_id=?", ("tenant-a",)).fetchone())
    return conn, row


def test_valid_active_window_stays_active():
    now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    conn, account = _account((now - timedelta(days=1)).isoformat(), (now + timedelta(days=20)).isoformat())
    state = evaluation_access_state(account, now=now)
    assert state["active"] is True
    assert state["evaluation_status"] == "EVALUATION_ACTIVE"
    conn.close()


@pytest.mark.parametrize("activated_at,ends_at", [
    ("2026-08-01T00:00:00+00:00", "not-a-time"),
    (None, "2026-09-01T00:00:00+00:00"),
    ("not-a-time", "2026-09-01T00:00:00+00:00"),
    ("2026-08-01T00:00:00", "2026-09-01T00:00:00+00:00"),
    ("2026-08-01T00:00:00+00:00", "2026-09-01T00:00:00"),
    ("2026-08-27T00:00:00+00:00", "2026-08-27T00:00:00+00:00"),
    ("2026-08-28T00:00:00+00:00", "2026-08-27T00:00:00+00:00"),
])
def test_invalid_active_window_is_unknown_and_inactive(activated_at, ends_at):
    conn, account = _account(activated_at, ends_at)
    state = evaluation_access_state(account, now=datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc))
    assert state["active"] is False
    assert state["plan"] == "expired"
    assert state["evaluation_status"] == "UNKNOWN"
    conn.close()


def test_valid_expired_window_is_expired():
    conn, account = _account("2026-08-01T00:00:00+00:00", "2026-08-20T00:00:00+00:00")
    state = evaluation_access_state(account, now=datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert state["active"] is False
    assert state["evaluation_status"] == "EXPIRED"
    conn.close()


def test_invalid_end_cannot_be_extended():
    conn, _ = _account("2026-08-01T00:00:00+00:00", "not-a-time")
    with pytest.raises(ValueError, match="evaluation_not_activated"):
        grant_evaluation_extension(
            conn,
            "tenant-a",
            days=1,
            reason="fixture",
            real_usage=True,
            insufficient_value_exposure=True,
            now=datetime(2026, 8, 27, tzinfo=timezone.utc),
        )
    conn.close()
