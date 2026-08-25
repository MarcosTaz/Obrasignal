import concurrent.futures
import sqlite3

import pytest

from fixture_storage_contract import (
    FIXTURE_STORE_CONTRACTS,
    fixture_tenant_owned_tables,
    verify_fixture_store,
)
from storage_contract import StorageContractError
from storage_migration_lock import run_serialized_schema_init
from storage_recovery import create_backup_artifact, verified_restore_drill


def _ensure_fixture_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS e2e_opportunity_fixtures (
            fixture_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(account_id, run_id),
            UNIQUE(account_id, source, external_id)
        );
        CREATE INDEX IF NOT EXISTS idx_e2e_fixture_account_run
            ON e2e_opportunity_fixtures(account_id, run_id);
        CREATE TABLE IF NOT EXISTS opportunity_workflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, source, external_id)
        );
        """
    )


def _insert_fixture(conn, account, run_id):
    fixture_id = f"e2e_{account}_{run_id}"
    conn.execute(
        """INSERT INTO e2e_opportunity_fixtures
           (fixture_id,account_id,run_id,source,external_id,created_at)
           VALUES(?,?,?,?,?,?)""",
        (fixture_id, account, run_id, "OBRASIGNAL_E2E_FIXTURE", fixture_id, "2026-08-25T00:00:00+00:00"),
    )
    return fixture_id


def test_fixture_store_owner_tenant_keys_and_index_are_explicit():
    fixture = FIXTURE_STORE_CONTRACTS["e2e_opportunity_fixtures"]
    workflow = FIXTURE_STORE_CONTRACTS["opportunity_workflow"]
    assert fixture.owner == "E2E fixture / e2e_fixture_api"
    assert fixture.tenant_column == "account_id"
    assert fixture.unique_keys == (
        ("fixture_id",), ("account_id", "run_id"), ("account_id", "source", "external_id")
    )
    assert fixture.required_indexes == ("idx_e2e_fixture_account_run",)
    assert workflow.tenant_column == "account_id"
    assert fixture_tenant_owned_tables() == {
        "e2e_opportunity_fixtures": "account_id",
        "opportunity_workflow": "account_id",
    }


def test_fixture_store_schema_rerun_and_uniques():
    conn = sqlite3.connect(":memory:")
    _ensure_fixture_schema(conn)
    _ensure_fixture_schema(conn)
    verify_fixture_store(conn)
    _insert_fixture(conn, "tenant-a", "run-1")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_fixture(conn, "tenant-a", "run-1")


def test_fixture_store_partial_schema_fails_closed_then_owner_init_repairs_additively():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE e2e_opportunity_fixtures (
            fixture_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(account_id, run_id),
            UNIQUE(account_id, source, external_id)
        );
        CREATE TABLE opportunity_workflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, source, external_id)
        );
        """
    )
    with pytest.raises(StorageContractError, match="missing_index=idx_e2e_fixture_account_run"):
        verify_fixture_store(conn)
    _ensure_fixture_schema(conn)
    verify_fixture_store(conn)


def test_fixture_store_concurrent_first_start_is_serializable(tmp_path):
    path = tmp_path / "fixture.db"
    def initialize():
        conn = sqlite3.connect(path, timeout=30)
        try:
            _ensure_fixture_schema(conn)
            conn.commit()
        finally:
            conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_serialized_schema_init, initialize, path) for _ in range(24)]
        for future in futures:
            future.result()
    conn = sqlite3.connect(path)
    try:
        verify_fixture_store(conn)
    finally:
        conn.close()


def test_fixture_workflow_cross_tenant_corruption_fails_closed():
    conn = sqlite3.connect(":memory:")
    _ensure_fixture_schema(conn)
    fixture_id = _insert_fixture(conn, "tenant-a", "run-1")
    conn.execute(
        """INSERT INTO opportunity_workflow
           (account_id,source,external_id,status,note,updated_at)
           VALUES(?,?,?,?,?,?)""",
        ("tenant-b", "OBRASIGNAL_E2E_FIXTURE", fixture_id, "REVIEWING", "wrong tenant", "2026-08-25T00:01:00+00:00"),
    )
    with pytest.raises(StorageContractError, match="workflow_tenant_mismatch_rows=1"):
        verify_fixture_store(conn)


def test_fixture_orphan_workflow_corruption_fails_closed():
    conn = sqlite3.connect(":memory:")
    _ensure_fixture_schema(conn)
    conn.execute(
        """INSERT INTO opportunity_workflow
           (account_id,source,external_id,status,note,updated_at)
           VALUES(?,?,?,?,?,?)""",
        ("tenant-a", "OBRASIGNAL_E2E_FIXTURE", "e2e_missing", "REVIEWING", "orphan", "2026-08-25T00:01:00+00:00"),
    )
    with pytest.raises(StorageContractError, match="orphan_fixture_workflow_rows=1"):
        verify_fixture_store(conn)


def test_fixture_cleanup_recovery_removes_only_owned_state_and_is_rerunnable():
    conn = sqlite3.connect(":memory:")
    _ensure_fixture_schema(conn)
    fixture_a = _insert_fixture(conn, "tenant-a", "run-1")
    fixture_b = _insert_fixture(conn, "tenant-b", "run-1")
    conn.execute(
        """INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at)
           VALUES(?,?,?,?,?,?)""",
        ("tenant-a", "OBRASIGNAL_E2E_FIXTURE", fixture_a, "PREPARING", "a", "2026-08-25T00:01:00+00:00"),
    )
    conn.execute(
        """INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at)
           VALUES(?,?,?,?,?,?)""",
        ("tenant-b", "OBRASIGNAL_E2E_FIXTURE", fixture_b, "PREPARING", "b", "2026-08-25T00:01:00+00:00"),
    )
    conn.commit()
    verify_fixture_store(conn)
    for _ in range(2):
        with conn:
            conn.execute(
                "DELETE FROM opportunity_workflow WHERE account_id=? AND source=? AND external_id=?",
                ("tenant-a", "OBRASIGNAL_E2E_FIXTURE", fixture_a),
            )
            conn.execute(
                "DELETE FROM e2e_opportunity_fixtures WHERE account_id=? AND fixture_id=?",
                ("tenant-a", fixture_a),
            )
    verify_fixture_store(conn)
    assert conn.execute("SELECT COUNT(*) FROM e2e_opportunity_fixtures WHERE account_id='tenant-a'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM opportunity_workflow WHERE account_id='tenant-a'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM e2e_opportunity_fixtures WHERE account_id='tenant-b'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM opportunity_workflow WHERE account_id='tenant-b'").fetchone()[0] == 1


def test_fixture_backup_restore_preserves_tenant_state(tmp_path):
    source = tmp_path / "fixture-source.db"
    conn = sqlite3.connect(source)
    _ensure_fixture_schema(conn)
    fixture_id = _insert_fixture(conn, "tenant-a", "run-1")
    conn.execute(
        """INSERT INTO opportunity_workflow
           (account_id,source,external_id,status,note,updated_at)
           VALUES(?,?,?,?,?,?)""",
        ("tenant-a", "OBRASIGNAL_E2E_FIXTURE", fixture_id, "PREPARING", "private", "2026-08-25T00:01:00+00:00"),
    )
    conn.commit()
    verify_fixture_store(conn)
    conn.close()

    artifact = create_backup_artifact(source, tmp_path / "backup", label="e2e-fixture-store")
    restored = tmp_path / "fixture-restored.db"
    verified_restore_drill(artifact["artifact"], artifact["manifest"], restored)
    conn = sqlite3.connect(restored)
    try:
        verify_fixture_store(conn)
        fixture = conn.execute(
            "SELECT account_id,run_id FROM e2e_opportunity_fixtures"
        ).fetchone()
        workflow = conn.execute(
            "SELECT account_id,status,note FROM opportunity_workflow"
        ).fetchone()
        assert fixture == ("tenant-a", "run-1")
        assert workflow == ("tenant-a", "PREPARING", "private")
    finally:
        conn.close()
