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

    The same authority rules apply within one staged batch. For a repeated canonical
    identity, a strictly newer explicit publisher instant replaces the earlier batch
    candidate before persistence; an older/equal/UNKNOWN later list item cannot win
    merely because it appears later in connector output. If the first candidate has
    UNKNOWN chronology, a later KNOWN instant may improve it, while another UNKNOWN
    candidate cannot displace it by list order alone.
    """
    ensure_signal_records(conn)
    accepted = []
    batch_positions = {}
    batch_instants = {}
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
        identity = (source, signal_type, external_id)
        incoming = _aware_source_instant(record.get("source_updated_at"))

        if identity in batch_positions:
            previous = batch_instants[identity]
            if previous is not None:
                if incoming is None or incoming <= previous:
                    continue
            elif incoming is None:
                continue
            position = batch_positions[identity]
            accepted[position] = record
            batch_instants[identity] = incoming
            continue

        row = conn.execute(
            "SELECT source_updated_at FROM signal_records "
            "WHERE source=? AND signal_type=? AND external_id=?",
            identity,
        ).fetchone()
        existing = _aware_source_instant(row[0]) if row else None
        if existing is not None:
            if incoming is None or incoming <= existing:
                continue
        elif row is not None and incoming is None:
            continue
        batch_positions[identity] = len(accepted)
        batch_instants[identity] = incoming
        accepted.append(record)
    return accepted


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _reconcile_legacy_tender_projection(conn, pending, accepted_tenders):
    """Restore the legacy Radar projection from canonical Signal truth.

    The legacy application commits before source-side temporal authority runs.
    Reconciliation is therefore mandatory for staged TENDER identities: accepted
    records project canonical content forward; rejected/rolled-back records project
    the prior canonical state back. This runs before downstream decision consumers.
    """
    if not _table_exists(conn, "tenders"):
        return {"reconciled": 0, "deleted": 0}

    accepted_last_seen = None
    if _table_exists(conn, "sync_runs"):
        run = conn.execute(
            "SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if run is not None:
            accepted_last_seen = run["finished_at"] if hasattr(run, "keys") else run[0]

    # Lazy imports avoid coupling source-only unit tests to the Flask application.
    import app as legacy_app
    from legacy_tender_projection import reconcile_staged_tender_projection

    return reconcile_staged_tender_projection(
        conn,
        pending,
        accepted_tender_identities=accepted_tenders,
        accepted_last_seen=accepted_last_seen,
        commercial_score=legacy_app.commercial_score,
        commit=True,
    )


def commit_staged_source_syncs(conn, *, accepted_tender_identities=None):
    """Atomically persist Signal, metadata, lifecycle and source cursors.

    The legacy opportunity transaction has already committed by the time this
    function is called. Within this second transaction all source-side state moves
    together. A malformed Signal identity/type, metadata/lifecycle write failure
    or cursor failure rolls back the complete source-side transaction, preventing
    silent data loss and preserving fail-closed cursor semantics.

    ``accepted_tender_identities`` is an optional mutable set used by composition
    code. It receives only TENDER identities admitted by publisher-time authority
    in the source transaction that actually commits. Any source rollback clears it.

    After the source transaction, staged TENDER identities are reconciled into the
    legacy ``tenders`` compatibility table from canonical Signal truth. This closes
    the two-transaction split-brain window before account decisioning can consume a
    stale late arrival. If the source transaction rolls back, reconciliation restores
    the prior canonical projection (or removes a first-time legacy row with no
    canonical Signal record) before the original persistence error is re-raised.

    Fetch health may already have been committed before this transaction begins.
    When canonical persistence fails, compensate that observation after rollback
    by degrading every staged source before re-raising the original error. Health
    compensation is best-effort per source: one failed health write must not stop
    attempts for the remaining staged sources, but no atomicity is claimed for
    those compensation writes themselves.
    """
    pending = staged_source_syncs()
    external_accepted = accepted_tender_identities
    if external_accepted is not None:
        external_accepted.clear()
    if not pending:
        return _empty_commit_result()

    committed_tenders = set()
    signal_records = 0
    metadata_records = 0
    lifecycle_records = 0
    cursors = 0

    try:
        for item in pending:
            records = _temporally_authoritative_records(conn, item.records)
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                source = str(record.get("source") or "").strip()
                external_id = str(record.get("external_id") or "").strip()
                if source and external_id and signal_type_of(record) == "TENDER":
                    committed_tenders.add((source, external_id))
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
        committed_tenders.clear()
        if external_accepted is not None:
            external_accepted.clear()

        compensation_errors = []
        for item in pending:
            try:
                record_source_ingestion_failure(conn, item.source, error=exc)
            except Exception as health_exc:
                compensation_errors.append((item.source, health_exc))
                continue

        projection_error = None
        try:
            _reconcile_legacy_tender_projection(conn, pending, set())
        except Exception as reconcile_exc:
            projection_error = reconcile_exc

        # The staged batch is terminal for this attempt regardless of which
        # compensation path failed. Never leak it into a later commit attempt.
        discard_staged_source_syncs()

        auxiliary = []
        if compensation_errors:
            failed_sources = ",".join(source for source, _ in compensation_errors)
            auxiliary.append(
                "source health compensation failed for "
                f"{failed_sources}: {type(compensation_errors[0][1]).__name__}"
            )
        if projection_error is not None:
            auxiliary.append(
                "legacy projection reconciliation failed: "
                f"{type(projection_error).__name__}"
            )
        if auxiliary:
            raise RuntimeError(f"{exc}; " + "; ".join(auxiliary)) from exc
        raise

    try:
        _reconcile_legacy_tender_projection(conn, pending, committed_tenders)
    except Exception as projection_exc:
        if external_accepted is not None:
            external_accepted.clear()
        raise RuntimeError(
            "source transaction committed but legacy projection reconciliation failed: "
            f"{type(projection_exc).__name__}: {projection_exc}"
        ) from projection_exc
    finally:
        discard_staged_source_syncs()

    if external_accepted is not None:
        external_accepted.update(committed_tenders)
    return {
        "sources": len(pending),
        "signal_records": signal_records,
        "metadata_records": metadata_records,
        "lifecycle_records": lifecycle_records,
        "cursors": cursors,
    }
