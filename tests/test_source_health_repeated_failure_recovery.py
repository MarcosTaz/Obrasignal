"""Data-truth probe: repeated projection failures may become unavailable, then recover without laundering history."""
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


def test_repeated_projection_failures_become_unavailable_then_recover_with_latest_failure_audit():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)

    first_success = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)
    failures = [
        datetime(2026, 8, 29, 3, 5, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 3, 10, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 3, 15, tzinfo=timezone.utc),
    ]
    recovered_at = datetime(2026, 8, 29, 3, 20, tzinfo=timezone.utc)

    record_source_result(
        conn,
        SOURCE,
        success=True,
        duration_ms=10,
        found=7,
        new_items=2,
        observed_at=first_success,
    )

    for index, failed_at in enumerate(failures, start=1):
        record_source_projection_failure(
            conn,
            SOURCE,
            error=sqlite3.OperationalError(f"synthetic projection failure {index}"),
            observed_at=failed_at,
        )
        failed = _item(conn, now=failed_at)
        assert failed["consecutive_failures"] == index
        assert failed["last_success"] == first_success.isoformat()
        assert failed["last_failed"] == failed_at.isoformat()
        assert failed["last_error"] == "projection_reconciliation_failed:OperationalError"
        assert failed["last_found"] == 7
        assert failed["last_new_items"] == 2

    unavailable = _item(conn, now=datetime(2026, 8, 29, 3, 16, tzinfo=timezone.utc))
    assert unavailable["health"] == "unavailable", (
        "REPEATED_PROJECTION_FAILURES_NOT_UNAVAILABLE: persistent represented-output failure "
        "must not remain merely degraded after the unavailable threshold"
    )
    assert unavailable["stats_state"] == "stale"
    assert unavailable["consecutive_failures"] == 3

    record_source_result(
        conn,
        SOURCE,
        success=True,
        duration_ms=12,
        found=8,
        new_items=1,
        observed_at=recovered_at,
    )
    recovered = _item(conn, now=datetime(2026, 8, 29, 3, 21, tzinfo=timezone.utc))

    assert recovered["health"] == "healthy", (
        "SOURCE_HEALTH_REPEATED_FAILURE_RECOVERY_DID_NOT_CONVERGE: successful represented "
        "recovery must clear unavailable current health"
    )
    assert recovered["freshness"] in {"fresh", "aging"}
    assert recovered["stats_state"] in {"current", "aging"}
    assert recovered["consecutive_failures"] == 0
    assert recovered["last_success"] == recovered_at.isoformat()
    assert recovered["last_failed"] == failures[-1].isoformat()
    assert recovered["last_error"] is None
    assert recovered["last_found"] == 8
    assert recovered["last_new_items"] == 1
