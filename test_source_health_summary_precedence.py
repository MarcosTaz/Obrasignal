"""Data-truth probe: coverage severity and empty-result claims must follow active-source authority."""
from datetime import datetime, timezone
import sqlite3

from source_health import (
    empty_result_context,
    ensure_source_health,
    record_source_projection_failure,
    record_source_result,
    source_health_contract,
)


TED = "TED"
BASE = "BASE"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def _contract(conn, *, now):
    return source_health_contract(conn, sources=[TED, BASE], now=now)


def test_coverage_status_precedence_tracks_active_source_authority():
    now = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)

    # BASE is healthy but past its 1440-minute expected refresh while still
    # inside its 2880-minute stale boundary: coverage must be aging, not current.
    conn = _conn()
    record_source_result(conn, TED, success=True, duration_ms=10, found=1, observed_at=datetime(2026, 8, 29, 11, 55, tzinfo=timezone.utc))
    record_source_result(conn, BASE, success=True, duration_ms=10, found=1, observed_at=datetime(2026, 8, 28, 11, 0, tzinfo=timezone.utc))
    aging = _contract(conn, now=now)
    assert aging["summary"]["coverage_status"] == "aging"
    assert aging["summary"]["all_expected_sources_current"] is False

    # A current source with an explicit failed attempt dominates another source's
    # aging state: degraded truth must not be softened to aging.
    record_source_projection_failure(
        conn,
        TED,
        error=sqlite3.OperationalError("synthetic projection failure"),
        observed_at=datetime(2026, 8, 29, 11, 58, tzinfo=timezone.utc),
    )
    degraded = _contract(conn, now=now)
    assert degraded["summary"]["coverage_status"] == "degraded"

    # An invalid success timestamp is unknown authority. With the other active
    # source healthy/current, summary must be unknown rather than current.
    conn = _conn()
    record_source_result(conn, TED, success=True, duration_ms=10, found=1, observed_at=datetime(2026, 8, 29, 11, 55, tzinfo=timezone.utc))
    record_source_result(conn, BASE, success=True, duration_ms=10, found=1, observed_at=datetime(2026, 8, 29, 11, 50, tzinfo=timezone.utc))
    conn.execute("UPDATE source_health SET last_success=? WHERE source=?", ("not-a-timestamp", BASE))
    conn.commit()
    unknown = _contract(conn, now=now)
    assert unknown["summary"]["coverage_status"] == "unknown"

    # Persistent failures only become unavailable once the last successful truth
    # is stale under that source's own authority window. Unavailable must dominate.
    conn = _conn()
    record_source_result(conn, TED, success=True, duration_ms=10, found=1, observed_at=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc))
    record_source_result(conn, BASE, success=True, duration_ms=10, found=1, observed_at=datetime(2026, 8, 29, 11, 50, tzinfo=timezone.utc))
    for minute in (30, 35, 40):
        record_source_projection_failure(
            conn,
            TED,
            error=sqlite3.OperationalError("synthetic persistent failure"),
            observed_at=datetime(2026, 8, 29, 11, minute, tzinfo=timezone.utc),
        )
    unavailable = _contract(conn, now=now)
    assert unavailable["summary"]["coverage_status"] == "unavailable"
    assert unavailable["summary"]["all_expected_sources_current"] is False


def test_empty_result_truth_never_becomes_market_absence_under_partial_coverage():
    now = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    conn = _conn()

    record_source_result(conn, TED, success=True, duration_ms=10, found=0, new_items=0, observed_at=datetime(2026, 8, 29, 11, 55, tzinfo=timezone.utc))
    # BASE intentionally has no successful observation: registered active coverage
    # is incomplete even though one active source returned zero records.
    partial = _contract(conn, now=now)

    assert partial["summary"]["expected_source_count"] == 2
    assert partial["summary"]["observed_expected_source_count"] == 1
    assert partial["summary"]["all_expected_sources_current"] is False
    assert partial["summary"]["market_absence_proven"] is False
    assert partial["summary"]["zero_market_claim_allowed"] is False

    empty = empty_result_context(partial, 0)
    assert empty["state"] == "coverage_unconfirmed", (
        "EMPTY_RESULT_AUTHORITY_DRIFT: zero observed records under partial active coverage must not become observed-empty-current or market absence"
    )
    assert empty["result_count"] == 0

    nonempty = empty_result_context(partial, 3)
    assert nonempty["state"] == "has_results"
    assert nonempty["result_count"] == 3
