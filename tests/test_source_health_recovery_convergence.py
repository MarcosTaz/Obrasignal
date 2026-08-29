"""Data-truth probe: a successful retry must recover public Source Health without erasing failure history."""
from datetime import datetime, timezone
import sqlite3

from source_health import (
    ensure_source_health,
    record_source_projection_failure,
    record_source_result,
    source_health_contract,
)


SOURCE = "UK_PROCUREMENT"


def _item(conn, *, now):
    return source_health_contract(conn, sources=[SOURCE], now=now)["items"][0]


def test_projection_failure_then_success_converges_health_without_erasing_failure_history():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)

    first_success = datetime(2026, 8, 29, 3, 0, tzinfo=timezone.utc)
    failed_at = datetime(2026, 8, 29, 3, 5, tzinfo=timezone.utc)
    recovered_at = datetime(2026, 8, 29, 3, 10, tzinfo=timezone.utc)

    record_source_result(
        conn,
        SOURCE,
        success=True,
        duration_ms=10,
        found=7,
        new_items=2,
        observed_at=first_success,
    )
    before_failure = _item(conn, now=datetime(2026, 8, 29, 3, 1, tzinfo=timezone.utc))
    assert before_failure["health"] == "healthy"
    assert before_failure["consecutive_failures"] == 0

    record_source_projection_failure(
        conn,
        SOURCE,
        error=sqlite3.OperationalError("synthetic projection failure"),
        observed_at=failed_at,
    )
    failed = _item(conn, now=datetime(2026, 8, 29, 3, 6, tzinfo=timezone.utc))
    assert failed["health"] == "degraded"
    assert failed["consecutive_failures"] == 1
    assert failed["last_success"] == before_failure["last_success"]
    assert failed["last_failed"] == failed_at.isoformat()
    assert failed["last_error"] == "projection_reconciliation_failed:OperationalError"
    assert failed["last_found"] == 7
    assert failed["last_new_items"] == 2

    record_source_result(
        conn,
        SOURCE,
        success=True,
        duration_ms=12,
        found=8,
        new_items=1,
        observed_at=recovered_at,
    )
    recovered = _item(conn, now=datetime(2026, 8, 29, 3, 11, tzinfo=timezone.utc))

    assert recovered["health"] == "healthy", (
        "SOURCE_HEALTH_RECOVERY_DID_NOT_CONVERGE: a successful represented retry must "
        "clear degraded current health"
    )
    assert recovered["freshness"] in {"fresh", "aging"}
    assert recovered["consecutive_failures"] == 0
    assert recovered["last_success"] == recovered_at.isoformat()
    assert recovered["last_error"] is None
    assert recovered["last_found"] == 8
    assert recovered["last_new_items"] == 1

    # Keep the last failure timestamp as audit history; recovery must not rewrite history.
    assert recovered["last_failed"] == failed_at.isoformat()
