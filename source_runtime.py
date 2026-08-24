"""Transaction boundary between global-source fetches and legacy persistence.

A connector may discover a new source watermark while ``app.sync_once`` is
still processing the returned opportunities. Advancing that watermark before
the main persistence succeeds could permanently skip records after a database
failure. This module stages cursor + source metadata + commercial lifecycle in
thread-local state and commits them only after the caller confirms the main sync
completed.
"""
from dataclasses import dataclass
import threading

from opportunity_lifecycle import persist_lifecycle_observations
from source_health import set_source_cursor
from source_metadata import persist_source_metadata


@dataclass
class StagedSourceSync:
    source: str
    records: list
    cursor: str | None


_state = threading.local()


def _pending():
    pending = getattr(_state, "pending", None)
    if pending is None:
        pending = {}
        _state.pending = pending
    return pending


def stage_source_sync(source, records, cursor):
    """Stage one source observation for commit after main tender persistence."""
    source = str(source or "").strip()
    if not source:
        raise ValueError("source is required")
    _pending()[source] = StagedSourceSync(source, list(records or []), cursor)


def staged_source_syncs():
    return list(_pending().values())


def discard_staged_source_syncs():
    _pending().clear()


def commit_staged_source_syncs(conn):
    """Atomically persist metadata, lifecycle observations and source cursors.

    The legacy opportunity transaction has already committed by the time this
    function is called. Within this second transaction, metadata, lifecycle and
    cursors move together: if any write fails, none of these source-side states
    advance. This is especially important for cancellation/completion tombstones.
    """
    pending = staged_source_syncs()
    if not pending:
        return {"sources": 0, "metadata_records": 0, "lifecycle_records": 0, "cursors": 0}
    metadata_records = 0
    lifecycle_records = 0
    cursors = 0
    try:
        for item in pending:
            metadata_records += persist_source_metadata(
                conn, item.records, commit=False
            )
            lifecycle_records += persist_lifecycle_observations(
                conn, item.records, commit=False
            )
            if item.cursor:
                set_source_cursor(conn, item.source, item.cursor, commit=False)
                cursors += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        discard_staged_source_syncs()
    return {
        "sources": len(pending),
        "metadata_records": metadata_records,
        "lifecycle_records": lifecycle_records,
        "cursors": cursors,
    }
