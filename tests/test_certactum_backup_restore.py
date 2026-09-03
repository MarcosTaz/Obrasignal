import hashlib
import sqlite3

import pytest

from vertical_apps.industrial_claims.backup_restore import (
    BackupRestoreError,
    create_verified_backup,
    restore_verified_backup,
)


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE evidence (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES (?, ?)", ("ev-1", "immutable test value"))
        connection.commit()


def test_backup_restore_round_trip_is_integrity_checked_and_digest_bound(tmp_path):
    database = tmp_path / "certactum.sqlite3"
    backup = tmp_path / "backups" / "certactum.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _database(database)

    receipt = create_verified_backup(database, backup)
    assert receipt.integrity_check == "ok"
    assert receipt.size_bytes > 0
    assert receipt.sha256 == hashlib.sha256(backup.read_bytes()).hexdigest()

    restored_receipt = restore_verified_backup(
        backup,
        restored,
        expected_sha256=receipt.sha256,
    )
    assert restored_receipt.sha256 == receipt.sha256
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM evidence WHERE id = 'ev-1'").fetchone() == (
            "immutable test value",
        )


def test_restore_rejects_tampered_backup_before_destination_mutation(tmp_path):
    database = tmp_path / "certactum.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _database(database)
    receipt = create_verified_backup(database, backup)
    restored.write_bytes(b"existing destination")
    backup.write_bytes(backup.read_bytes() + b"tamper")

    with pytest.raises(BackupRestoreError, match="SHA-256 mismatch"):
        restore_verified_backup(backup, restored, expected_sha256=receipt.sha256)
    assert restored.read_bytes() == b"existing destination"


def test_restore_requires_explicit_valid_expected_digest(tmp_path):
    database = tmp_path / "certactum.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _database(database)
    create_verified_backup(database, backup)

    with pytest.raises(BackupRestoreError, match="expected SHA-256"):
        restore_verified_backup(backup, tmp_path / "restored.sqlite3", expected_sha256="")
