"""Transaction boundary between global-source fetches and durable source state.

A connector may discover a new source watermark while ``app.sync_once`` is
still processing any legacy TENDER projection. Advancing that watermark before
persistence succeeds could permanently skip records after a database failure.

This module therefore stages normalized signals in thread-local state and commits
the canonical Signal record, source metadata, lifecycle state and source cursor in
one source-side transaction after the legacy transaction has succeeded.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import threading

from opportunity_lifecycle import persist_lifecycle_observations
from signal_store import ensure_signal_records, persist_signal_records, signal_type_of
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


def _aware_source_instant(value):
    """Parse only explicitly timezone-aware source instants; never guess a zone."""
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _temporally_authoritative_records(conn, records):
    """Accept only observations that cannot manufacture publisher chronology.

    Processing/arrival time has no business authority here. Once durable truth has
    an explicit timezone-aware publisher instant, replacement requires an incoming
    explicit timezone-aware instant that is strictly newer. Equal instants establish
    no causal winner and fail closed. Missing, malformed or timezone-naive incoming
    timestamps have UNKNOWN position relative to known durable time and therefore
    also fail closed rather than being promoted by arrival order.

    If durable publisher time is UNKNOWN and an incoming observation is also
    UNKNOWN, their relative causal order remains UNKNOWN, so an existing canonical
    record must not be replaced merely because another observation was processed
    later. A provable incoming publisher instant may still improve previously
    UNKNOWN temporal evidence without claiming retroactive ordering among unknown
    observations.
    """
    ensure_signal_records(conn)
    accepted = []
    for record in records or []:
        if not isinstance(record, Mapping):
            accepted.append(record)
            continue
        source = str(record.get("source") or "").strip()
        external_id = str(record.get("external_id") or "").strip()
        if not source or not external_id:
            accepted.append(record)
            continue
        signal_type = signal_type_of(record)
        row = conn.execute(
            "SELECT source_updated_at FROM signal_records "
            "WHERE source=? AND signal_type=? AND external_id=?",
            (source, signal_type, external_id),
        ).fetchone()
        existing = _aware_source_instant(row[0]) if row else None
        incoming = _aware_source_instant(record.get("source_updated_at"))
        if existing is not None:
            if incoming is None or incoming <= existing:
                continue
        elif row is not None and incoming is None:
            continue
        accepted.append(record)
    return accepted


def commit_staged_source_syncs(conn):
    """Atomically persist Signal, metadata, lifecycle and source cursors.

    The legacy opportunity transaction has already committed by the time this
    function is called. Within this second transaction all source-side state moves
    together. A malformed Signal identity/type, metadata/lifecycle write failure
    or cursor failure rolls back the complete source-side transaction, preventing
    silent data loss and preserving fail-closed cursor semantics.

    Fetch health may already have been committed before this transaction begins.
    When canonical persistence fails, compensate that observation after rollback
    by degrading every staged source before re-raising the original error.
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
            records = _temporally_authoritative_records(conn, item.records)
            signal_records += persist_signal_records(
                conn,
                records,
                expected_source=item.source,
                commit=False,
            )
            metadata_records += persist_source_metadata(
                conn, records, commit=False
            )
            lifecycle_records += persist_lifecycle_observations(
                conn, records, commit=False
            )
            if item.cursor:
                set_source_cursor(conn, item.source, item.cursor, commit=False)
                cursors += 1
        conn.commit()
    except Exception as exc:
        conn.rollback()
        compensation_errors = []
        for item in pending:
            try:
                record_source_ingestion_failure(conn, item.source, error=exc)
            except Exception as health_exc:
                compensation_errors.append((item.source, health_exc))
                continue
        if compensation_errors:
            failed_sources = ",".join(source for source, _ in compensation_errors)
            first_error = compensation_errors[0][1]
            raise RuntimeError(
                f"{exc}; source health compensation failed for {failed_sources}: "
                f"{type(first_error).__name__}"
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
