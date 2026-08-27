"""Persistence reliability acceptance for Watchlist on the current trust spine."""
import concurrent.futures
import sqlite3

import opportunity_workflow as workflow
from storage_migration_lock import run_serialized_schema_init
from storage_recovery import create_backup_artifact, verified_restore_drill


def _connect(path):
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tenders(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL, UNIQUE(source, external_id))")


def _initialize(path):
    conn = _connect(path)
    try:
        _ensure_tenders(conn)
        workflow.ensure_workflow_table(conn)
        conn.commit()
    finally:
        conn.close()


def test_watchlist_first_start_is_serialized_rerunnable_and_preserves_legacy_row(tmp_path):
    path = tmp_path / "watchlist.db"
    conn = _connect(path)
    _ensure_tenders(conn)
    conn.execute("""CREATE TABLE opportunity_workflow(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT NOT NULL,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        status TEXT NOT NULL,
        note TEXT,
        updated_at TEXT NOT NULL,
        UNIQUE(account_id, source, external_id)
    )""")
    conn.execute("INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at) VALUES(?,?,?,?,?,?)",
                 ("tenant-a","TED","legacy","REVIEWING","keep","2026-08-27T00:00:00+00:00"))
    conn.commit(); conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(lambda _: (run_serialized_schema_init(lambda: _initialize(path), path), True)[1], range(24)))

    conn = _connect(path)
    row = conn.execute("SELECT status,note,priority,saved_at FROM opportunity_workflow WHERE account_id='tenant-a'").fetchone()
    assert tuple(row) == ("REVIEWING", "keep", "NORMAL", None)
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(opportunity_workflow)")}
    assert {"idx_opportunity_workflow_account_saved", "idx_opportunity_workflow_account_status_priority"} <= indexes
    conn.close()


def test_watchlist_mutations_are_tenant_isolated(tmp_path):
    path = tmp_path / "tenant-watchlist.db"
    _initialize(path)
    conn = _connect(path)
    conn.execute("INSERT INTO tenders(id,source,external_id) VALUES(1,'TED','shared')")
    conn.commit()

    workflow.save_opportunity(conn, "tenant-a", 1)
    workflow.save_opportunity(conn, "tenant-b", 1)
    workflow.update_saved_opportunity(conn, "tenant-a", 1, status="REVIEWING", priority="HIGH", note="a-private", note_provided=True)

    a = workflow.get_saved_opportunity(conn, "tenant-a", 1)
    b = workflow.get_saved_opportunity(conn, "tenant-b", 1)
    assert (a["status"], a["priority"], a["note"]) == ("REVIEWING", "HIGH", "a-private")
    assert (b["status"], b["priority"], b["note"]) == ("NEW", "NORMAL", None)

    assert workflow.unsave_opportunity(conn, "tenant-a", 1) is True
    assert workflow.get_saved_opportunity(conn, "tenant-a", 1) is None
    assert workflow.get_saved_opportunity(conn, "tenant-b", 1) is not None
    preserved = workflow.get_workflow(conn, "tenant-a", "TED", "shared")
    assert (preserved["status"], preserved["priority"], preserved["note"]) == ("REVIEWING", "HIGH", "a-private")
    conn.close()


def test_watchlist_backup_restore_preserves_tenant_membership_and_fields(tmp_path):
    source = tmp_path / "watchlist-source.db"
    _initialize(source)
    conn = _connect(source)
    conn.execute("INSERT INTO tenders(id,source,external_id) VALUES(1,'TED','shared')")
    conn.commit()
    workflow.save_opportunity(conn, "tenant-a", 1)
    workflow.save_opportunity(conn, "tenant-b", 1)
    workflow.update_saved_opportunity(conn, "tenant-a", 1, priority="HIGH", note="a-private", note_provided=True)
    conn.close()

    artifact = create_backup_artifact(source, tmp_path / "backup", label="watchlist", source_revision="watchlist-current-spine")
    restored = tmp_path / "watchlist-restored.db"
    verified_restore_drill(artifact["artifact"], artifact["manifest"], restored)

    conn = _connect(restored)
    rows = conn.execute("SELECT account_id,status,priority,note,saved_at FROM opportunity_workflow ORDER BY account_id").fetchall()
    assert [r["account_id"] for r in rows] == ["tenant-a", "tenant-b"]
    assert rows[0]["priority"] == "HIGH" and rows[0]["note"] == "a-private" and rows[0]["saved_at"] is not None
    assert rows[1]["priority"] == "NORMAL" and rows[1]["note"] is None and rows[1]["saved_at"] is not None
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
