from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

import app
from storage_contract import verify_database
from storage_migration_lock import run_serialized_schema_init


def _table_names(path):
    conn = sqlite3.connect(str(path))
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def _verify_database_path(path):
    conn = sqlite3.connect(str(path))
    try:
        verify_database(conn)
    finally:
        conn.close()


def test_g9_concurrent_first_start_converges_to_one_valid_schema(monkeypatch, tmp_path):
    path = tmp_path / "concurrent-first-start.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))

    workers = 12
    barrier = threading.Barrier(workers)

    def initialize(_index):
        barrier.wait(timeout=10)
        run_serialized_schema_init(app.init_db, path)
        conn = app.db()
        try:
            return conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(initialize, range(workers)))

    assert outcomes == ["ok"] * workers
    expected = {
        "tenders",
        "sync_runs",
        "accounts",
        "company_profiles",
        "opportunity_decisions",
        "opportunity_events",
        "opportunity_workflow",
        "billing_webhook_events",
    }
    assert expected <= _table_names(path)
    _verify_database_path(path)


def test_g9_concurrent_start_from_partial_historical_schema_is_additive_and_preserves_rows(monkeypatch, tmp_path):
    path = tmp_path / "concurrent-historical-start.sqlite"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE tenders(
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
        )"""
    )
    conn.execute(
        "INSERT INTO tenders(source,external_id,title) VALUES(?,?,?)",
        ("TED", "historical-preserved", "Historical preserved opportunity"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))

    workers = 12
    barrier = threading.Barrier(workers)

    def initialize(_index):
        barrier.wait(timeout=10)
        run_serialized_schema_init(app.init_db, path)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert list(pool.map(initialize, range(workers))) == [True] * workers

    conn = app.db()
    try:
        row = conn.execute(
            "SELECT title FROM tenders WHERE source=? AND external_id=?",
            ("TED", "historical-preserved"),
        ).fetchone()
        assert row["title"] == "Historical preserved opportunity"
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tenders)")}
        assert {"published_at", "match_reason", "priority_label", "priority_class", "market"} <= columns
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()
    _verify_database_path(path)
