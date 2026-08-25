import sqlite3


def test_db_only_opens_and_configures_connection(monkeypatch, tmp_path):
    import app

    path = tmp_path / "plain.db"
    monkeypatch.setattr(app, "DB", str(path))
    conn = app.db()
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == app.SQLITE_BUSY_TIMEOUT_SECONDS * 1000
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    finally:
        conn.close()


def test_init_db_is_idempotent_and_preserves_existing_rows(monkeypatch, tmp_path):
    import app

    path = tmp_path / "startup.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    app.init_db()
    conn = app.db()
    conn.execute(
        "INSERT INTO tenders(source, external_id, title) VALUES(?, ?, ?)",
        ("TED", "preserved", "Existing opportunity"),
    )
    conn.commit()
    conn.close()

    app.init_db()
    conn = app.db()
    try:
        row = conn.execute("SELECT title FROM tenders WHERE external_id='preserved'").fetchone()
        assert row["title"] == "Existing opportunity"
        expected = {"tenders", "sync_runs", "accounts", "company_profiles", "opportunity_decisions", "opportunity_events", "opportunity_workflow"}
        actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert expected <= actual
    finally:
        conn.close()


def test_normal_connection_executes_no_schema_ddl(monkeypatch, tmp_path):
    import app

    path = tmp_path / "traced.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    app.init_db()
    statements = []
    conn = app.db()
    conn.set_trace_callback(statements.append)
    try:
        conn.execute("SELECT COUNT(*) FROM tenders").fetchone()
    finally:
        conn.close()
    assert not any(statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ")) for statement in statements)
