import concurrent.futures
import sqlite3

import pytest

from storage_contract import (
    PREBUILD_CONTRACTS,
    REGISTERED_ADDITIVE_MIGRATIONS,
    StorageContractError,
    contract_fingerprint,
    tenant_owned_tables,
    verify_push_delivery_integrity,
    verify_schema,
)
from storage_migration_lock import run_serialized_schema_init
from storage_recovery import create_backup_artifact, verified_restore_drill


def _event_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS opportunity_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL DEFAULT 'default',
            event_key TEXT NOT NULL UNIQUE,
            tender_id INTEGER,
            source TEXT,
            event_type TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            delivered_at TEXT
        )"""
    )


def _ensure_push_schema(conn: sqlite3.Connection) -> None:
    """Mirror #329 owner DDL; this verifier never becomes a second writer."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_devices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            installation_id TEXT NOT NULL UNIQUE,
            expo_push_token TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            binding_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_error TEXT,
            revoked_at TEXT
        )"""
    )
    device_cols = {row[1] for row in conn.execute("PRAGMA table_info(push_devices)").fetchall()}
    if "revoked_at" not in device_cols:
        conn.execute("ALTER TABLE push_devices ADD COLUMN revoked_at TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_push_devices_account ON push_devices(account_id)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS push_deliveries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            push_device_id INTEGER NOT NULL,
            ticket_id TEXT,
            submitted_at TEXT,
            last_error TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            next_attempt_at TEXT,
            expo_push_token TEXT,
            receipt_status TEXT,
            receipt_checked_at TEXT,
            receipt_error TEXT,
            failed_at TEXT,
            UNIQUE(event_id,push_device_id)
        )"""
    )
    delivery_cols = {row[1] for row in conn.execute("PRAGMA table_info(push_deliveries)").fetchall()}
    additions = {
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "last_attempt_at": "TEXT",
        "next_attempt_at": "TEXT",
        "expo_push_token": "TEXT",
        "receipt_status": "TEXT",
        "receipt_checked_at": "TEXT",
        "receipt_error": "TEXT",
        "failed_at": "TEXT",
    }
    for column, ddl in additions.items():
        if column not in delivery_cols:
            conn.execute(f"ALTER TABLE push_deliveries ADD COLUMN {column} {ddl}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_push_deliveries_event_device ON push_deliveries(event_id,push_device_id)"
    )


def _insert_event(conn: sqlite3.Connection, account: str, key: str) -> int:
    cur = conn.execute(
        """INSERT INTO opportunity_events(account_id,event_key,event_type,created_at)
           VALUES(?,?,?,?)""",
        (account, key, "new_high_match", "2026-08-25T00:00:00+00:00"),
    )
    return int(cur.lastrowid)


def _insert_device(conn: sqlite3.Connection, account: str, installation: str, token: str) -> int:
    cur = conn.execute(
        """INSERT INTO push_devices(
               account_id,installation_id,expo_push_token,platform,binding_id,created_at,updated_at
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            account,
            installation,
            token,
            "android",
            "binding-" + installation,
            "2026-08-25T00:00:00+00:00",
            "2026-08-25T00:00:00+00:00",
        ),
    )
    return int(cur.lastrowid)


def test_push_prebuild_contract_is_exact_and_noncanonical_by_default():
    devices = PREBUILD_CONTRACTS["push_devices"]
    deliveries = PREBUILD_CONTRACTS["push_deliveries"]
    assert devices.owner == "Notification Delivery / notification_events"
    assert devices.tenant_column == "account_id"
    assert devices.unique_keys == (("installation_id",), ("expo_push_token",))
    assert devices.required_indexes == ("idx_push_devices_account",)
    assert deliveries.owner == "Notification Delivery / notification_events"
    assert deliveries.tenant_column is None
    assert deliveries.unique_keys == (("event_id", "push_device_id"),)
    assert deliveries.required_indexes == ("idx_push_deliveries_event_device",)
    assert tenant_owned_tables(include_prebuild=True)["push_devices"] == "account_id"
    assert "push_devices" not in tenant_owned_tables()
    assert contract_fingerprint(include_runtime=True) != contract_fingerprint(
        include_runtime=True, include_prebuild=True
    )
    assert REGISTERED_ADDITIVE_MIGRATIONS["push_devices"] == ("revoked_at",)
    assert REGISTERED_ADDITIVE_MIGRATIONS["push_deliveries"] == (
        "attempt_count", "last_attempt_at", "next_attempt_at", "expo_push_token",
        "receipt_status", "receipt_checked_at", "receipt_error", "failed_at",
    )


def test_push_schema_unique_indexes_and_idempotency_keys_are_enforced():
    conn = sqlite3.connect(":memory:")
    _event_schema(conn)
    _ensure_push_schema(conn)
    verify_schema(conn, {
        "push_devices": PREBUILD_CONTRACTS["push_devices"],
        "push_deliveries": PREBUILD_CONTRACTS["push_deliveries"],
    })
    event_id = _insert_event(conn, "tenant-a", "tenant-a:event-1")
    device_id = _insert_device(conn, "tenant-a", "install-a-0001", "ExpoPushToken[a]")
    conn.execute(
        "INSERT INTO push_deliveries(event_id,push_device_id) VALUES(?,?)",
        (event_id, device_id),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO push_deliveries(event_id,push_device_id) VALUES(?,?)",
            (event_id, device_id),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_device(conn, "tenant-b", "install-a-0001", "ExpoPushToken[b]")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_device(conn, "tenant-b", "install-b-0001", "ExpoPushToken[a]")


def test_push_old_partial_schema_migrates_additively_and_reruns():
    conn = sqlite3.connect(":memory:")
    _event_schema(conn)
    conn.executescript(
        """
        CREATE TABLE push_devices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            installation_id TEXT NOT NULL UNIQUE,
            expo_push_token TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            binding_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_error TEXT
        );
        CREATE TABLE push_deliveries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            push_device_id INTEGER NOT NULL,
            ticket_id TEXT,
            submitted_at TEXT,
            last_error TEXT,
            UNIQUE(event_id,push_device_id)
        );
        """
    )
    _ensure_push_schema(conn)
    _ensure_push_schema(conn)
    verify_schema(conn, {
        "push_devices": PREBUILD_CONTRACTS["push_devices"],
        "push_deliveries": PREBUILD_CONTRACTS["push_deliveries"],
    })


def test_push_first_start_is_serialized_and_concurrent_safe(tmp_path):
    path = tmp_path / "push.db"

    def initialize():
        conn = sqlite3.connect(path, timeout=30)
        try:
            _event_schema(conn)
            _ensure_push_schema(conn)
            conn.commit()
        finally:
            conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_serialized_schema_init, initialize, path) for _ in range(24)]
        for future in futures:
            future.result()

    conn = sqlite3.connect(path)
    try:
        verify_schema(conn, {
            "push_devices": PREBUILD_CONTRACTS["push_devices"],
            "push_deliveries": PREBUILD_CONTRACTS["push_deliveries"],
        })
    finally:
        conn.close()


def test_push_delivery_tenant_event_device_chain_fails_closed():
    conn = sqlite3.connect(":memory:")
    _event_schema(conn)
    _ensure_push_schema(conn)
    event_a = _insert_event(conn, "tenant-a", "tenant-a:event-1")
    device_a = _insert_device(conn, "tenant-a", "install-a-0001", "ExpoPushToken[a]")
    device_b = _insert_device(conn, "tenant-b", "install-b-0001", "ExpoPushToken[b]")
    conn.execute(
        "INSERT INTO push_deliveries(event_id,push_device_id) VALUES(?,?)",
        (event_a, device_a),
    )
    verify_push_delivery_integrity(conn)
    conn.execute(
        "INSERT INTO push_deliveries(event_id,push_device_id) VALUES(?,?)",
        (event_a, device_b),
    )
    with pytest.raises(StorageContractError, match="tenant_chain_mismatch_rows=1"):
        verify_push_delivery_integrity(conn)


def test_push_retry_ledger_corruption_is_fail_closed():
    conn = sqlite3.connect(":memory:")
    _event_schema(conn)
    _ensure_push_schema(conn)
    event_id = _insert_event(conn, "tenant-a", "tenant-a:event-1")
    device_id = _insert_device(conn, "tenant-a", "install-a-0001", "ExpoPushToken[a]")
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,attempt_count,submitted_at,ticket_id,next_attempt_at
           ) VALUES(?,?,1,?,NULL,?)""",
        (
            event_id,
            device_id,
            "2026-08-25T00:00:00+00:00",
            "2026-08-25T00:01:00+00:00",
        ),
    )
    with pytest.raises(StorageContractError, match="push delivery integrity failed"):
        verify_push_delivery_integrity(conn)


def test_push_revocation_tombstone_preserves_historical_delivery_identity():
    conn = sqlite3.connect(":memory:")
    _event_schema(conn)
    _ensure_push_schema(conn)
    event_id = _insert_event(conn, "tenant-a", "tenant-a:event-1")
    device_id = _insert_device(conn, "tenant-a", "install-a-0001", "ExpoPushToken[a]")
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,last_attempt_at,expo_push_token,receipt_status
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            event_id,
            device_id,
            "ticket-1",
            "2026-08-25T00:00:00+00:00",
            1,
            "2026-08-25T00:00:00+00:00",
            "ExpoPushToken[a]",
            "provider_accepted",
        ),
    )
    conn.execute(
        """UPDATE push_devices
           SET expo_push_token='revoked:1:opaque',binding_id='rotated-binding',revoked_at='2026-08-25T00:05:00+00:00'
           WHERE id=?""",
        (device_id,),
    )
    verify_push_delivery_integrity(conn)
    row = conn.execute(
        "SELECT push_device_id,expo_push_token FROM push_deliveries WHERE event_id=?",
        (event_id,),
    ).fetchone()
    assert row == (device_id, "ExpoPushToken[a]")


def test_push_backup_restore_preserves_tenants_tombstones_and_retry_ledger(tmp_path):
    source = tmp_path / "push-source.db"
    conn = sqlite3.connect(source)
    _event_schema(conn)
    _ensure_push_schema(conn)
    event_a = _insert_event(conn, "tenant-a", "tenant-a:event-1")
    event_b = _insert_event(conn, "tenant-b", "tenant-b:event-1")
    device_a = _insert_device(conn, "tenant-a", "install-a-0001", "ExpoPushToken[a]")
    device_b = _insert_device(conn, "tenant-b", "install-b-0001", "ExpoPushToken[b]")
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,attempt_count,last_attempt_at,next_attempt_at,expo_push_token,last_error
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            event_a,
            device_a,
            2,
            "2026-08-25T00:00:00+00:00",
            "2026-08-25T00:02:00+00:00",
            "ExpoPushToken[a]",
            "transport_Timeout",
        ),
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,last_attempt_at,expo_push_token,receipt_status
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            event_b,
            device_b,
            "ticket-b",
            "2026-08-25T00:00:00+00:00",
            1,
            "2026-08-25T00:00:00+00:00",
            "ExpoPushToken[b]",
            "provider_accepted",
        ),
    )
    conn.execute(
        """UPDATE push_devices
           SET expo_push_token='revoked:2:opaque',binding_id='rotated-b',revoked_at='2026-08-25T00:05:00+00:00'
           WHERE id=?""",
        (device_b,),
    )
    conn.commit()
    verify_push_delivery_integrity(conn)
    conn.close()

    artifact = create_backup_artifact(
        source,
        tmp_path / "backup",
        label="push-persistence-contract",
        source_revision="push-prebuild-contract-test",
    )
    restored = tmp_path / "push-restored.db"
    verified_restore_drill(artifact["artifact"], artifact["manifest"], restored)

    conn = sqlite3.connect(restored)
    try:
        verify_schema(conn, {
            "push_devices": PREBUILD_CONTRACTS["push_devices"],
            "push_deliveries": PREBUILD_CONTRACTS["push_deliveries"],
        })
        verify_push_delivery_integrity(conn)
        devices = conn.execute(
            "SELECT account_id,installation_id,expo_push_token,revoked_at FROM push_devices ORDER BY account_id"
        ).fetchall()
        deliveries = conn.execute(
            "SELECT event_id,push_device_id,attempt_count,next_attempt_at,receipt_status,expo_push_token FROM push_deliveries ORDER BY event_id"
        ).fetchall()
        assert len(devices) == 2 and len(deliveries) == 2
        assert devices[0][0] == "tenant-a" and devices[1][0] == "tenant-b"
        assert devices[1][2].startswith("revoked:") and devices[1][3] is not None
        assert deliveries[0][2] == 2 and deliveries[0][3] is not None
        assert deliveries[1][4] == "provider_accepted"
        assert deliveries[1][5] == "ExpoPushToken[b]"
    finally:
        conn.close()
