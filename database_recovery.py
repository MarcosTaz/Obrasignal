"""Verified online SQLite backups for the production ObraSignal datastore.

The application currently runs a single SQLite database on a Render persistent
volume.  SQLite's online backup API is used so a backup represents one
consistent database snapshot even while readers/writers are active.  Every
artifact is then restored into a fresh temporary SQLite file and compared with
the backup before it is accepted as verified.

This is an application-level recovery layer.  It intentionally does not claim
that the infrastructure provider's disk-snapshot restore has been exercised.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

DEFAULT_INTERVAL_SECONDS = 12 * 60 * 60
DEFAULT_KEEP = 2
SQLITE_TIMEOUT_SECONDS = 30
_STATE_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "status": "not_run",
    "last_verified_at": None,
    "last_error": None,
    "backup_bytes": None,
    "table_count": None,
    "schema_sha256": None,
}
_WORKER_LOCK = threading.Lock()
_WORKER_STARTED = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%SZ")


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute(f"PRAGMA busy_timeout={SQLITE_TIMEOUT_SECONDS * 1000}")
    return conn


def _integrity_check(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    result = str(row[0] if row else "").strip().lower()
    if result != "ok":
        raise RuntimeError(f"sqlite_integrity_check_failed:{result or 'empty'}")


def _user_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _quoted_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _row_counts(conn: sqlite3.Connection, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        row = conn.execute(f"SELECT COUNT(*) FROM {_quoted_identifier(table)}").fetchone()
        counts[table] = int(row[0] if row else 0)
    return counts


def _schema_digest(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name, tbl_name"
    ).fetchall()
    canonical = "\n".join("\x1f".join(str(value) for value in row) for row in rows)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _set_state(**values: Any) -> None:
    with _STATE_LOCK:
        _STATE.update(values)


def recovery_health() -> dict[str, Any]:
    """Return bounded recovery state suitable for the public health endpoint."""
    with _STATE_LOCK:
        state = dict(_STATE)
    verified_at = state.get("last_verified_at")
    age_seconds = None
    if verified_at:
        try:
            dt = datetime.fromisoformat(str(verified_at).replace("Z", "+00:00"))
            age_seconds = max(0, int((_utc_now() - dt).total_seconds()))
        except ValueError:
            pass
    return {
        "status": state.get("status"),
        "last_verified_at": verified_at,
        "age_seconds": age_seconds,
        "backup_bytes": state.get("backup_bytes"),
        "table_count": state.get("table_count"),
        "last_error": state.get("last_error"),
    }


def _rotate(directory: Path, keep: int) -> None:
    keep = max(1, int(keep))
    artifacts = sorted(directory.glob("obrasignal-backup-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in artifacts[keep:]:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def create_verified_backup(
    db_path: str | os.PathLike[str],
    *,
    backup_dir: str | os.PathLike[str] | None = None,
    keep: int = DEFAULT_KEEP,
) -> dict[str, Any]:
    """Create an online backup and prove it restores into a clean SQLite DB.

    A backup is accepted only after:
      1. SQLite online backup completes;
      2. PRAGMA integrity_check succeeds on the backup;
      3. the backup is restored to a fresh temporary database;
      4. integrity_check succeeds on the restored database; and
      5. schema digest and per-table row counts are identical between the
         backup and the restored database.
    """
    source_path = Path(db_path).resolve()
    if not source_path.exists():
        error = f"database_not_found:{source_path.name}"
        _set_state(status="error", last_error=error)
        raise FileNotFoundError(error)

    directory = Path(backup_dir).resolve() if backup_dir else source_path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    partial = directory / f".obrasignal-backup-{stamp}-{os.getpid()}.partial.db"
    final = directory / f"obrasignal-backup-{stamp}-{os.getpid()}.db"
    restore_probe = directory / f".obrasignal-restore-probe-{stamp}-{os.getpid()}.db"

    source = backup = restored = None
    try:
        source = _connect(source_path)
        backup = _connect(partial)
        source.backup(backup)
        backup.commit()
        _integrity_check(backup)
        tables = _user_tables(backup)
        backup_counts = _row_counts(backup, tables)
        backup_schema = _schema_digest(backup)
        backup.close()
        backup = None
        source.close()
        source = None

        # Atomic publication: no file with the stable backup pattern exists
        # until the first integrity check has succeeded.
        os.replace(partial, final)

        backup = _connect(final)
        restored = _connect(restore_probe)
        backup.backup(restored)
        restored.commit()
        _integrity_check(restored)
        restored_tables = _user_tables(restored)
        restored_counts = _row_counts(restored, restored_tables)
        restored_schema = _schema_digest(restored)
        if tables != restored_tables:
            raise RuntimeError("restore_table_set_mismatch")
        if backup_counts != restored_counts:
            raise RuntimeError("restore_row_count_mismatch")
        if backup_schema != restored_schema:
            raise RuntimeError("restore_schema_mismatch")

        size = final.stat().st_size
        verified_at = _utc_now().isoformat()
        _set_state(
            status="verified",
            last_verified_at=verified_at,
            last_error=None,
            backup_bytes=size,
            table_count=len(tables),
            schema_sha256=backup_schema,
        )
        _rotate(directory, keep)
        return {
            "status": "verified",
            "verified_at": verified_at,
            "backup_bytes": size,
            "table_count": len(tables),
            "schema_sha256": backup_schema,
        }
    except Exception as exc:
        _set_state(status="error", last_error=f"{type(exc).__name__}:{exc}")
        raise
    finally:
        for conn in (restored, backup, source):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        for path in (partial, restore_probe):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def start_recovery_worker(db_path: str | os.PathLike[str]) -> threading.Thread | None:
    """Periodically renew the verified local recovery artifact.

    Only one worker is started per process.  The production blueprint currently
    uses one Gunicorn worker, so this does not create competing backup loops.
    """
    global _WORKER_STARTED
    enabled = (os.getenv("OBRASIGNAL_BACKUP_ENABLED", "1") or "1").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        _set_state(status="disabled", last_error=None)
        return None
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return None
        _WORKER_STARTED = True

    interval = max(3600, int(os.getenv("OBRASIGNAL_BACKUP_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))))
    keep = max(1, int(os.getenv("OBRASIGNAL_BACKUP_KEEP", str(DEFAULT_KEEP))))
    backup_dir = os.getenv("OBRASIGNAL_BACKUP_DIR") or None

    def loop() -> None:
        while True:
            time.sleep(interval)
            try:
                create_verified_backup(db_path, backup_dir=backup_dir, keep=keep)
            except Exception:
                # Failure is surfaced through recovery_health and production
                # monitoring; the ingestion/service process must remain alive.
                pass

    thread = threading.Thread(target=loop, name="obrasignal-recovery", daemon=True)
    thread.start()
    return thread
