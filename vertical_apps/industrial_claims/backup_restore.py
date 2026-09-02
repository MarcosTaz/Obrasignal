from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class BackupRestoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupReceipt:
    path: str
    sha256: str
    size_bytes: int
    created_at: str
    integrity_check: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "integrity_check": self.integrity_check,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity(path: Path) -> str:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupRestoreError("SQLite integrity check failed") from exc
    result = str(row[0] if row else "").strip().lower()
    if result != "ok":
        raise BackupRestoreError(f"SQLite integrity check failed: {result or 'no result'}")
    return result


def create_verified_backup(database: str | Path, destination: str | Path) -> BackupReceipt:
    source = Path(database)
    target = Path(destination)
    if not source.is_file():
        raise BackupRestoreError("source database does not exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary) as target_connection:
            source_connection.backup(target_connection)
        integrity = _integrity(temporary)
        digest = _sha256(temporary)
        size = temporary.stat().st_size
        if size <= 0:
            raise BackupRestoreError("backup is empty")
        os.replace(temporary, target)
        return BackupReceipt(
            path=str(target),
            sha256=digest,
            size_bytes=size,
            created_at=datetime.now(timezone.utc).isoformat(),
            integrity_check=integrity,
        )
    finally:
        temporary.unlink(missing_ok=True)


def restore_verified_backup(backup: str | Path, destination: str | Path, *, expected_sha256: str) -> BackupReceipt:
    source = Path(backup)
    target = Path(destination)
    expected = str(expected_sha256 or "").strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise BackupRestoreError("expected SHA-256 is required")
    if not source.is_file():
        raise BackupRestoreError("backup does not exist")
    actual = _sha256(source)
    if actual != expected:
        raise BackupRestoreError("backup SHA-256 mismatch")
    integrity = _integrity(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".restore.tmp", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary) as target_connection:
            source_connection.backup(target_connection)
        _integrity(temporary)
        if _sha256(temporary) != actual:
            raise BackupRestoreError("restored database digest does not match verified backup")
        os.replace(temporary, target)
        return BackupReceipt(
            path=str(target),
            sha256=actual,
            size_bytes=target.stat().st_size,
            created_at=datetime.now(timezone.utc).isoformat(),
            integrity_check=integrity,
        )
    finally:
        temporary.unlink(missing_ok=True)
