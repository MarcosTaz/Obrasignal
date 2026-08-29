from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from factory_cloud.assurance_store import SCHEMA_VERSION


class AssuranceBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupReceipt:
    source: str
    backup: str
    created_at: str
    sha256: str
    schema_version: int
    integrity: str


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _integrity(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0] if row else "unknown")


def _schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM assurance_meta WHERE key='schema_version'").fetchone()
    except sqlite3.Error as exc:
        raise AssuranceBackupError("assurance schema metadata unavailable") from exc
    if not row:
        raise AssuranceBackupError("assurance schema version missing")
    try:
        return int(row[0])
    except (TypeError, ValueError) as exc:
        raise AssuranceBackupError("invalid assurance schema version") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(source: str | Path, destination: str | Path) -> BackupReceipt:
    source_path = Path(source)
    destination_path = Path(destination)
    if not source_path.is_file():
        raise AssuranceBackupError("source assurance database missing")
    if source_path.resolve() == destination_path.resolve():
        raise AssuranceBackupError("backup destination must differ from source")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise AssuranceBackupError("backup destination already exists")

    try:
        with _connect(source_path) as source_conn:
            if _integrity(source_conn) != "ok":
                raise AssuranceBackupError("source integrity check failed")
            source_version = _schema_version(source_conn)
            if source_version != SCHEMA_VERSION:
                raise AssuranceBackupError("source schema version is not current")
            with _connect(destination_path) as backup_conn:
                source_conn.backup(backup_conn)
        with _connect(destination_path) as verify_conn:
            integrity = _integrity(verify_conn)
            version = _schema_version(verify_conn)
        if integrity != "ok" or version != source_version:
            destination_path.unlink(missing_ok=True)
            raise AssuranceBackupError("backup verification failed")
    except Exception:
        if destination_path.exists() and destination_path.stat().st_size == 0:
            destination_path.unlink(missing_ok=True)
        raise

    return BackupReceipt(
        source=str(source_path),
        backup=str(destination_path),
        created_at=datetime.now(timezone.utc).isoformat(),
        sha256=_sha256(destination_path),
        schema_version=version,
        integrity=integrity,
    )


def restore_backup(backup: str | Path, destination: str | Path, *, expected_sha256: str) -> None:
    backup_path = Path(backup)
    destination_path = Path(destination)
    if not backup_path.is_file():
        raise AssuranceBackupError("backup file missing")
    if len(expected_sha256) != 64 or _sha256(backup_path) != expected_sha256:
        raise AssuranceBackupError("backup digest mismatch")
    if destination_path.exists():
        raise AssuranceBackupError("restore destination already exists")
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(backup_path) as backup_conn:
        if _integrity(backup_conn) != "ok":
            raise AssuranceBackupError("backup integrity check failed")
        version = _schema_version(backup_conn)
        if version != SCHEMA_VERSION:
            raise AssuranceBackupError("backup schema version is not current")
        with _connect(destination_path) as restored_conn:
            backup_conn.backup(restored_conn)

    with _connect(destination_path) as restored_conn:
        if _integrity(restored_conn) != "ok" or _schema_version(restored_conn) != version:
            destination_path.unlink(missing_ok=True)
            raise AssuranceBackupError("restored database verification failed")


def receipt_json(receipt: BackupReceipt) -> str:
    return json.dumps(receipt.__dict__, sort_keys=True, separators=(",", ":"))
