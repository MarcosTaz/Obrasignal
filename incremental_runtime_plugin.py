"""Reusable runtime wiring for opt-in incremental procurement sources.

Legacy production sources are still composed in ``preload``. New global sources
can be added additively through this wrapper without growing that compatibility
module with one source-specific block per market. The plugin preserves the same
production gate, source health accounting and transactional cursor staging used
by the existing Wave-1 connectors.
"""
import time

from procurement_quality import dedupe_records
from source_health import get_source_cursor, record_source_result
from source_runtime import stage_source_sync


def _record_health(db, source, *, success, started, found=0, error=None):
    conn = db()
    try:
        record_source_result(
            conn,
            source,
            success=success,
            duration_ms=int((time.perf_counter() - started) * 1000),
            found=int(found or 0),
            error=error,
        )
    finally:
        conn.close()


def build_incremental_source_wrapper(
    previous_fetch,
    *,
    source,
    fetch_incremental,
    source_enabled,
    record_blocked,
    db,
):
    """Wrap the current aggregate fetcher with one gated incremental source.

    ``fetch_incremental`` must accept ``watermark=`` and return ``(rows, cursor)``.
    The cursor is staged only after a complete source fetch and is committed later
    by the existing sync transaction. Source failure is isolated like the legacy
    connector loop: health is marked failed while already-fetched sources survive.
    """
    source = str(source or "").upper()
    if not source:
        raise ValueError("incremental runtime source is required")
    if not callable(previous_fetch) or not callable(fetch_incremental):
        raise TypeError("runtime fetchers must be callable")

    def fetch_with_incremental_source(*args, **kwargs):
        base_rows = previous_fetch(*args, **kwargs)
        rows = list(base_rows or [])

        if not source_enabled(source):
            record_blocked(source)
            return dedupe_records(rows)

        started = time.perf_counter()
        try:
            conn = db()
            try:
                watermark = get_source_cursor(conn, source)
            finally:
                conn.close()

            found, cursor = fetch_incremental(watermark=watermark)
            found = list(found or [])
            stage_source_sync(source, found, cursor)
            rows.extend(found)
            _record_health(db, source, success=True, started=started, found=len(found))
        except Exception as exc:
            _record_health(db, source, success=False, started=started, error=exc)

        return dedupe_records(rows)

    inherited = set(getattr(previous_fetch, "_obrasignal_incremental_sources", ()))
    fetch_with_incremental_source._obrasignal_incremental_sources = frozenset(inherited | {source})
    fetch_with_incremental_source.__name__ = f"fetch_with_{source.lower()}"
    return fetch_with_incremental_source


def install_incremental_source(
    app_module,
    *,
    source,
    fetch_incremental,
    source_enabled,
    record_blocked,
):
    """Install one source exactly once on ``app_module.fetch_base``."""
    source = str(source or "").upper()
    previous = app_module.fetch_base
    if source in set(getattr(previous, "_obrasignal_incremental_sources", ())):
        return previous
    wrapped = build_incremental_source_wrapper(
        previous,
        source=source,
        fetch_incremental=fetch_incremental,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
        db=app_module.db,
    )
    app_module.fetch_base = wrapped
    return wrapped
