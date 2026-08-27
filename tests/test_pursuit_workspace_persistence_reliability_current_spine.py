"""Persistence reliability acceptance for Pursuit Workspace on current trust spine."""
import concurrent.futures
import sqlite3

import pytest
import pursuit_workspace as workspace
from storage_migration_lock import run_serialized_schema_init
from storage_recovery import create_backup_artifact, verified_restore_drill


def _connect(path):
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_tenders(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS tenders(
        id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT, buyer TEXT,
        country TEXT, value TEXT, deadline TEXT, publication_date TEXT, url TEXT
    )""")


def _initialize(path):
    conn = _connect(path)
    try:
        _ensure_tenders(conn)
        workspace.ensure_workspace_tables(conn)
        conn.commit()
    finally:
        conn.close()


def test_pursuit_first_start_is_serialized_and_rerunnable(tmp_path):
    path = tmp_path / "pursuit.db"
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(lambda _: (run_serialized_schema_init(lambda: _initialize(path), path), True)[1], range(24)))
    conn = _connect(path)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"pursuit_workspaces","pursuit_workspace_blockers","pursuit_workspace_notes","pursuit_workspace_questions"} <= tables
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_pursuit_workspace_and_children_are_tenant_isolated(tmp_path):
    path = tmp_path / "pursuit-tenants.db"
    _initialize(path)
    conn = _connect(path)
    conn.execute("INSERT INTO tenders(id,source,external_id,title) VALUES(1,'TED','shared','Shared')")
    conn.commit()
    a = workspace.create_workspace(conn, "tenant-a", 1)
    b = workspace.create_workspace(conn, "tenant-b", 1)
    assert a["workspace_id"] != b["workspace_id"]
    blocker = workspace.add_blocker(conn, "tenant-a", 1, "a-private")
    workspace.add_note(conn, "tenant-b", 1, "b-private")

    with pytest.raises(LookupError, match="blocker_not_found"):
        workspace.resolve_blocker(conn, "tenant-b", 1, blocker["blocker_id"])
    a_view = workspace.workspace_view(conn, "tenant-a", 1)
    b_view = workspace.workspace_view(conn, "tenant-b", 1)
    assert [x["title"] for x in a_view["blockers"]] == ["a-private"]
    assert a_view["notes"] == []
    assert [x["body"] for x in b_view["notes"]] == ["b-private"]
    assert b_view["blockers"] == []
    conn.close()


def test_pursuit_parent_delete_with_children_fails_closed_not_orphaned(tmp_path):
    path = tmp_path / "pursuit-delete.db"
    _initialize(path)
    conn = _connect(path)
    conn.execute("INSERT INTO tenders(id,source,external_id,title) VALUES(1,'TED','x','X')")
    conn.commit()
    ws = workspace.create_workspace(conn, "tenant-a", 1)
    workspace.add_note(conn, "tenant-a", 1, "keep-child")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM pursuit_workspaces WHERE workspace_id=?", (ws["workspace_id"],))
    conn.rollback()
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert workspace.get_workspace(conn, "tenant-a", 1) is not None
    conn.close()


def test_pursuit_backup_restore_preserves_tenant_workspace_graph(tmp_path):
    source = tmp_path / "pursuit-source.db"
    _initialize(source)
    conn = _connect(source)
    conn.execute("INSERT INTO tenders(id,source,external_id,title) VALUES(1,'TED','shared','Shared')")
    conn.commit()
    workspace.create_workspace(conn, "tenant-a", 1)
    workspace.create_workspace(conn, "tenant-b", 1)
    workspace.add_note(conn, "tenant-a", 1, "a-private")
    workspace.add_blocker(conn, "tenant-b", 1, "b-private")
    conn.close()

    artifact = create_backup_artifact(source, tmp_path / "backup", label="pursuit", source_revision="pursuit-current-spine")
    restored = tmp_path / "pursuit-restored.db"
    verified_restore_drill(artifact["artifact"], artifact["manifest"], restored)

    conn = _connect(restored)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    rows = conn.execute("SELECT account_id,opportunity_id FROM pursuit_workspaces ORDER BY account_id").fetchall()
    assert [tuple(r) for r in rows] == [("tenant-a",1),("tenant-b",1)]
    assert conn.execute("SELECT body FROM pursuit_workspace_notes").fetchone()[0] == "a-private"
    assert conn.execute("SELECT title FROM pursuit_workspace_blockers").fetchone()[0] == "b-private"
    conn.close()
