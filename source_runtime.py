"""Transaction boundary between global-source fetches and durable source state.

A connector may discover a new source watermark while ``app.sync_once`` is
still processing any legacy TENDER projection. Advancing that watermark before
persistence succeeds could permanently skip records after a database failure.

This module therefore stages normalized signals in thread-local state and commits
the canonical Signal record, source metadata, lifecycle state and source cursor in
one source-side transaction after the legacy transaction has succeeded.
"""
from dataclasses import dataclass
import threading

from opportunity_lifecycle import persist_lifecycle_observations
from signal_store import persist_signal_records
from source_health import record_source_ingestion_failure, set_source_cursor
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
    """Stage one source observation for commit after legacy persistence."""
    source = str(source or "").strip()
    if not source:
        raise ValueError("source is required")
    _pending()[source] = StagedSourceSync(source, list(records or []), cursor)


def staged_source_syncs():
    return list(_pending().values())


def discard_staged_source_syncs():
    _pending().clear()


def _empty_commit_result():
    return {
        "sources": 0,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 0,
    }


def commit_staged_source_syncs(conn):
    """Atomically persist Signal, metadata, lifecycle and source cursors.

    The legacy opportunity transaction has already committed by the time this
    function is called. Within this second transaction all source-side state moves
    together. A malformed Signal identity/type, metadata/lifecycle write failure
    or cursor failure rolls back the complete source-side transaction, preventing
    silent data loss and preserving fail-closed cursor semantics.

    Fetch health may have been committed before this transaction begins. When the
    canonical transaction fails, compensate that observation after rollback by
    degrading each staged source. This keeps the last successful fetch evidence for
    diagnosis without allowing it to masquerade as successful durable ingestion.
    """
    pending = staged_source_syncs()
    if not pending:
        return _empty_commit_result()
    signal_records = 0
    metadata_records = 0
    lifecycle_records = 0
    cursors = 0
    try:
        for item in pending:
            signal_records += persist_signal_records(
                conn,
                item.records,
                expected_source=item.source,
                commit=False,
            )
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
    except Exception as exc:
        conn.rollback()
        compensation_error = None
        for item in pending:
            try:
                record_source_ingestion_failure(conn, item.source, error=exc)
            except Exception as health_exc:
                compensation_error = health_exc
                break
        if compensation_error is not None:
            raise RuntimeError(
                f"{exc}; source health compensation failed: {type(compensation_error).__name__}"
            ) from exc
        raise
    finally:
        discard_staged_source_syncs()
    return {
        "sources": len(pending),
        "signal_records": signal_records,
        "metadata_records": metadata_records,
        "lifecycle_records": lifecycle_records,
        "cursors": cursors,
    }
