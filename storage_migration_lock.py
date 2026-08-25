"""Process-safe serialization boundary for additive SQLite startup migrations."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import threading
from typing import Callable, Iterator


class MigrationLockError(RuntimeError):
    pass


_PROCESS_LOCK = threading.RLock()


def _database_path(value: str | os.PathLike[str]) -> Path | None:
    raw = str(value)
    if raw == ":memory:":
        return None
    return Path(raw).expanduser().resolve()


@contextmanager
def schema_migration_lock(db_path: str | os.PathLike[str]) -> Iterator[None]:
    """Serialize schema initialization for the current process and POSIX host."""
    database = _database_path(db_path)
    with _PROCESS_LOCK:
        if database is None:
            yield
            return
        if not database.parent.exists():
            raise MigrationLockError("database parent directory does not exist")
        lock_path = Path(str(database) + ".migration.lock")
        try:
            handle = lock_path.open("a+b")
        except OSError as exc:
            raise MigrationLockError("cannot open schema migration lock") from exc
        try:
            if os.name == "posix":
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except (ImportError, OSError) as exc:
                    raise MigrationLockError("cannot acquire POSIX schema migration lock") from exc
            yield
        finally:
            if os.name == "posix":
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError):
                    pass
            handle.close()


def run_serialized_schema_init(initializer: Callable[[], None], db_path: str | os.PathLike[str]) -> None:
    with schema_migration_lock(db_path):
        initializer()
