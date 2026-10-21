from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class AssuranceBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupRecord:
    source: Path
    backup: Path
    sha256: str
    integrity: str


def _integrity(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "missing"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(source: str | Path, destination: str | Path) -> BackupRecord:
    source_path = Path(source)
    destination_path = Path(destination)
    if not source_path.is_file():
        raise AssuranceBackupError("source database does not exist")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.resolve() == source_path.resolve():
        raise AssuranceBackupError("backup destination must differ from source")
    with sqlite3.connect(source_path) as src, sqlite3.connect(destination_path) as dst:
        src.backup(dst)
    integrity = _integrity(destination_path)
    if integrity != "ok":
        raise AssuranceBackupError(f"backup integrity check failed: {integrity}")
    return BackupRecord(source_path, destination_path, _sha256(destination_path), integrity)


def restore_backup(backup: str | Path, destination: str | Path) -> BackupRecord:
    backup_path = Path(backup)
    destination_path = Path(destination)
    if not backup_path.is_file():
        raise AssuranceBackupError("backup database does not exist")
    integrity = _integrity(backup_path)
    if integrity != "ok":
        raise AssuranceBackupError(f"source backup integrity check failed: {integrity}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup_path) as src, sqlite3.connect(destination_path) as dst:
        src.backup(dst)
    restored_integrity = _integrity(destination_path)
    if restored_integrity != "ok":
        raise AssuranceBackupError(f"restored database integrity check failed: {restored_integrity}")
    return BackupRecord(backup_path, destination_path, _sha256(destination_path), restored_integrity)
