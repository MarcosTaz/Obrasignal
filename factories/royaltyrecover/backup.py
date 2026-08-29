from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from repository import RoyaltyRepository


@dataclass(frozen=True)
class BackupResult:
    path: str
    sha256: str
    integrity: str
    table_count: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_repository(repository: RoyaltyRepository, destination: str) -> BackupResult:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError("backup destination already exists; refusing to overwrite")
    target = sqlite3.connect(str(path))
    try:
        repository.conn.backup(target)
        target.commit()
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"backup integrity check failed: {integrity}")
        table_count = target.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    finally:
        target.close()
    return BackupResult(path=str(path), sha256=_sha256_file(path), integrity=integrity, table_count=table_count)


def verify_backup(path: str, expected_sha256: str | None = None) -> BackupResult:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(path)
    sha = _sha256_file(file_path)
    if expected_sha256 is not None and sha != expected_sha256:
        raise RuntimeError("backup SHA-256 mismatch")
    conn = sqlite3.connect(str(file_path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"backup integrity check failed: {integrity}")
        table_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    finally:
        conn.close()
    return BackupResult(path=str(file_path), sha256=sha, integrity=integrity, table_count=table_count)
