"""Cross-process coordination for the production web instance.

ObraSignal serves customer traffic and refreshes procurement sources from the same
Render instance. Gunicorn uses more than one HTTP worker for availability, but
only one worker may own ingestion and scheduled push delivery. POSIX file locks
provide a process-lifetime leader lease without introducing another service or
sharing customer data outside the existing persistent store.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

_LEADER_HANDLE = None
_LEADER_STATE: bool | None = None


def _lock_path(kind: str) -> Path:
    root = Path((os.getenv("OBRASIGNAL_RUNTIME_LOCK_DIR") or "/tmp").strip() or "/tmp")
    root.mkdir(parents=True, exist_ok=True)
    return root / f"obrasignal-{kind}.lock"


@contextmanager
def serialized_startup():
    """Serialize schema/WAL startup work across Gunicorn worker processes."""
    path = _lock_path("startup")
    handle = path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def acquire_runtime_leader() -> bool:
    """Return True only in the worker that owns background runtime duties.

    The winning file descriptor stays open for the process lifetime. A replacement
    Gunicorn worker can acquire the lease automatically after the previous leader
    exits, while follower workers never start duplicate ingestion/push schedulers.
    """
    global _LEADER_HANDLE, _LEADER_STATE
    if _LEADER_STATE is not None:
        return _LEADER_STATE

    path = _lock_path("background-leader")
    handle = path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        _LEADER_STATE = False
        return False

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _LEADER_HANDLE = handle
    _LEADER_STATE = True
    return True
