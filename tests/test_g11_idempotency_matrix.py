from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

import app
from notification_events import register_push_device
from opportunity_workflow import save_opportunity
from storage_migration_lock import run_serialized_schema_init


def _conn(path):
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def _seed(path):
    app.DB = str(path)
    run_serialized_schema_init(app.init_db, path)
    conn = _conn(path)
    try:
        cur = conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,score,first_seen,last_seen
            ) VALUES(?,?,?,?,datetime('now'),datetime('now'))""",
            ("TED", "g11-retry", "Idempotency opportunity", 88),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def test_g11_duplicate_save_retries_create_one_stable_watchlist_row(monkeypatch, tmp_path):
    path = tmp_path / "g11-save.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))
    opportunity_id = _seed(path)

    first_conn = _conn(path)
    try:
        first = save_opportunity(first_conn, "acct-g11", opportunity_id)
        first_saved_at = first["saved_at"]
        first_updated_at = first["updated_at"]
        for _ in range(8):
            replay = save_opportunity(first_conn, "acct-g11", opportunity_id)
            assert replay["saved_at"] == first_saved_at
            assert replay["updated_at"] == first_updated_at
    finally:
        first_conn.close()

    conn = _conn(path)
    try:
        rows = conn.execute(
            """SELECT account_id,source,external_id,status,saved_at,updated_at
               FROM opportunity_workflow
               WHERE account_id=? AND source=? AND external_id=?""",
            ("acct-g11", "TED", "g11-retry"),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["saved_at"] == first_saved_at
        assert rows[0]["updated_at"] == first_updated_at
    finally:
        conn.close()


def test_g11_concurrent_duplicate_saves_converge_to_one_canonical_row(monkeypatch, tmp_path):
    path = tmp_path / "g11-save-concurrent.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))
    opportunity_id = _seed(path)
    workers = 12
    barrier = threading.Barrier(workers)

    def save_once(_index):
        conn = _conn(path)
        try:
            barrier.wait(timeout=10)
            return save_opportunity(conn, "acct-g11", opportunity_id)["saved_at"]
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        saved_times = list(pool.map(save_once, range(workers)))

    assert len(set(saved_times)) == 1
    conn = _conn(path)
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS n, MIN(saved_at) AS min_saved, MAX(saved_at) AS max_saved
               FROM opportunity_workflow
               WHERE account_id=? AND source=? AND external_id=?""",
            ("acct-g11", "TED", "g11-retry"),
        ).fetchone()
        assert row["n"] == 1
        assert row["min_saved"] == row["max_saved"] == saved_times[0]
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_g11_identical_push_registration_retry_preserves_binding_and_single_device(monkeypatch, tmp_path):
    path = tmp_path / "g11-device.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))
    _seed(path)

    conn = _conn(path)
    try:
        first = register_push_device(
            conn,
            "acct-g11",
            "installation-g11-0001",
            "ExpoPushToken[g11-idempotent]",
            "ios",
        )
        for _ in range(8):
            replay = register_push_device(
                conn,
                "acct-g11",
                "installation-g11-0001",
                "ExpoPushToken[g11-idempotent]",
                "ios",
            )
            assert replay["binding_id"] == first["binding_id"]
        rows = conn.execute(
            "SELECT id,binding_id,revoked_at FROM push_devices WHERE installation_id=?",
            ("installation-g11-0001",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["binding_id"] == first["binding_id"]
        assert rows[0]["revoked_at"] is None
    finally:
        conn.close()
