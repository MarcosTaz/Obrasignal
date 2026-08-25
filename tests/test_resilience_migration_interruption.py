import sqlite3

import pytest


def test_canonical_startup_busy_timeout_is_not_recovery_proof(monkeypatch, tmp_path):
    """Configured SQLite wait is not evidence of serialized migration recovery."""
    import app

    path = tmp_path / "startup.db"
    monkeypatch.setattr(app, "DB", str(path))
    conn = app.db()
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == app.SQLITE_BUSY_TIMEOUT_SECONDS * 1000
    finally:
        conn.close()

    with pytest.raises(ImportError):
        from storage_migration_lock import run_serialized_schema_init  # noqa: F401


def test_partial_schema_rerun_preserves_existing_row(monkeypatch, tmp_path):
    """A repository-local partial old schema converges without row loss."""
    import app

    path = tmp_path / "partial.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE tenders(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,
      external_id TEXT NOT NULL,
      title TEXT,
      description TEXT,
      buyer TEXT,
      country TEXT,
      cpv TEXT,
      value TEXT,
      deadline TEXT,
      publication_date TEXT,
      url TEXT,
      score INTEGER DEFAULT 0,
      first_seen TEXT,
      last_seen TEXT,
      UNIQUE(source,external_id)
    );
    INSERT INTO tenders(source,external_id,title) VALUES('LOCAL','keep','preserve');
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr(app, "DB", str(path))
    app.init_db()
    app.init_db()

    conn = app.db()
    try:
        row = conn.execute("SELECT title FROM tenders WHERE source='LOCAL' AND external_id='keep'").fetchone()
        assert row is not None and row[0] == "preserve"
        columns = {r[1] for r in conn.execute("PRAGMA table_info(tenders)").fetchall()}
        assert {"published_at", "match_reason", "priority_label", "priority_class", "market"} <= columns
    finally:
        conn.close()
