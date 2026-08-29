"""Transaction boundary between global-source fetches and durable source state.

A connector may discover a new source watermark while ``app.sync_once`` is
still processing any legacy TENDER projection. Advancing that watermark before
persistence succeeds could permanently skip records after a database failure.

This module therefore stages normalized signals in thread-local state and commits
the canonical Signal record, optional opportunity history, source metadata,
lifecycle state and source cursor in one source-side transaction after the legacy
transaction has succeeded.
"""
from dataclasses import dataclass
import threading

from capability_registry import capability
from opportunity_change_history import persist_change_observations
from opportunity_lifecycle import persist_lifecycle_observations
from signal_store import persist_signal_records
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
    """Stage one source observation for commit after legacy persistence."""
    source = str(source or "").strip()
    if not source:
        raise ValueError("source is required")
    _pending()[source] = StagedSourceSync(source, list(records or []), cursor)


def staged_source_syncs():
    return list(_pending().values())


def discard_staged_source_syncs():
    _pending().clear()


def _change_history_runtime_enabled():
    """Only deliberately promoted PILOT/ENABLED states may execute history."""
    return capability("OPPORTUNITY_CHANGE_HISTORY").state in {"PILOT", "ENABLED"}


def _history_projection(records):
    """Expose source-native revision/amendment semantics without connector coupling.

    The generic change contract monitors ``source_version``. Connectors may already
    expose that name or one of the supported native revision aliases. CanadaBuys
    uses ``amendment_number``/``amendment_date``. Projection happens on a copy so
    current Signal persistence retains the connector's original canonical shape.
    """
    projected = []
    revision_aliases = (
        "amendment_number",
        "revision_id",
        "amendment_id",
        "corrigendum_id",
        "native_revision",
        "release_id",
    )
    for record in records or []:
        if not isinstance(record, dict):
            projected.append(record)
            continue
        item = dict(record)
        if not item.get("source_version"):
            for key in revision_aliases:
                if item.get(key) not in (None, ""):
                    item["source_version"] = item.get(key)
                    break
        if not item.get("source_updated_at") and item.get("amendment_date"):
            item["source_updated_at"] = item.get("amendment_date")
        projected.append(item)
    return projected


def _empty_commit_result():
    return {
        "sources": 0,
        "signal_records": 0,
        "metadata_records": 0,
        "lifecycle_records": 0,
        "cursors": 0,
    }


def commit_staged_source_syncs(conn):
    """Atomically persist optional history, Signal, metadata, lifecycle and cursors.

    Change History is currently RESEARCH and therefore skipped by the canonical
    registry. If a separate authorized maturity decision later promotes it to
    PILOT/ENABLED, it must observe the previous canonical state before Signal upsert
    replaces it, so it runs first inside the transaction. States outside
    PILOT/ENABLED disable history without blocking Signal, metadata, lifecycle or
    cursor persistence. Any deliberately enabled history failure still rolls back
    the complete source-side transaction.
    """
    pending = staged_source_syncs()
    if not pending:
        return _empty_commit_result()
    signal_records = 0
    metadata_records = 0
    lifecycle_records = 0
    cursors = 0
    history_enabled = _change_history_runtime_enabled()
    try:
        for item in pending:
            if history_enabled:
                persist_change_observations(
                    conn,
                    _history_projection(item.records),
                    commit=False,
                )
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
    except Exception:
        conn.rollback()
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
