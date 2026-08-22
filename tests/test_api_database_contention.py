import sqlite3


def test_api_database_waits_for_bounded_account_bootstrap_contention(monkeypatch, tmp_path):
    """Requests following profile persistence must outwait SQLite's default lock window."""
    import app

    db_path = tmp_path / "contention.db"
    monkeypatch.setattr(app, "DB", str(db_path))

    conn = app.db()
    try:
        busy_timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        conn.close()

    default_conn = sqlite3.connect(":memory:")
    try:
        default_busy_timeout_ms = default_conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        default_conn.close()

    assert busy_timeout_ms == app.SQLITE_BUSY_TIMEOUT_SECONDS * 1000
    assert busy_timeout_ms > default_busy_timeout_ms
