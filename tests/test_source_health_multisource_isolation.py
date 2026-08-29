"""Data-truth probe: one source's repeated projection failures and recovery must not mutate another source's health authority."""
from datetime import datetime, timezone
import sqlite3

from source_health import (
    ensure_source_health,
    record_source_projection_failure,
    record_source_result,
    source_health_contract,
)


FAILING_SOURCE = "UK_PROCUREMENT"
CONTROL_SOURCE = "TED"


def _items(conn, *, now):
    payload = source_health_contract(conn, sources=[FAILING_SOURCE, CONTROL_SOURCE], now=now)
    return {item["source"]: item for item in payload["items"]}


def test_repeated_failure_and_recovery_are_source_isolated():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)

    failing_initial = datetime(2026, 8, 28, 4, 0, tzinfo=timezone.utc)
    control_initial = datetime(2026, 8, 29, 4, 0, tzinfo=timezone.utc)
    failures = [
        datetime(2026, 8, 29, 4, 5, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 4, 10, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 4, 15, tzinfo=timezone.utc),
    ]
    recovered_at = datetime(2026, 8, 29, 4, 20, tzinfo=timezone.utc)

    record_source_result(
        conn,
        FAILING_SOURCE,
        success=True,
        duration_ms=10,
        found=7,
        new_items=2,
        observed_at=failing_initial,
    )
    record_source_result(
        conn,
        CONTROL_SOURCE,
        success=True,
        duration_ms=9,
        found=11,
        new_items=4,
        observed_at=control_initial,
    )

    for index, failed_at in enumerate(failures, start=1):
        record_source_projection_failure(
            conn,
            FAILING_SOURCE,
            error=sqlite3.OperationalError(f"synthetic isolated projection failure {index}"),
            observed_at=failed_at,
        )

        current = _items(conn, now=failed_at)
        failing = current[FAILING_SOURCE]
        control = current[CONTROL_SOURCE]

        assert failing["consecutive_failures"] == index
        assert failing["last_failed"] == failed_at.isoformat()
        assert control["health"] == "healthy", (
            "SOURCE_HEALTH_CROSS_SOURCE_CONTAMINATION: failure authority from one source must not "
            "degrade another source"
        )
        assert control["consecutive_failures"] == 0
        assert control["last_failed"] is None
        assert control["last_error"] is None
        assert control["last_success"] == control_initial.isoformat()
        assert control["last_found"] == 11
        assert control["last_new_items"] == 4

    unavailable = _items(
        conn,
        now=datetime(2026, 8, 29, 4, 16, tzinfo=timezone.utc),
    )
    assert unavailable[FAILING_SOURCE]["health"] == "unavailable"
    assert unavailable[FAILING_SOURCE]["stats_state"] == "stale"
    assert unavailable[CONTROL_SOURCE]["health"] == "healthy"

    record_source_result(
        conn,
        FAILING_SOURCE,
        success=True,
        duration_ms=12,
        found=8,
        new_items=1,
        observed_at=recovered_at,
    )

    recovered = _items(
        conn,
        now=datetime(2026, 8, 29, 4, 21, tzinfo=timezone.utc),
    )
    failing = recovered[FAILING_SOURCE]
    control = recovered[CONTROL_SOURCE]

    assert failing["health"] == "healthy"
    assert failing["consecutive_failures"] == 0
    assert failing["last_failed"] == failures[-1].isoformat()
    assert failing["last_success"] == recovered_at.isoformat()

    assert control["health"] == "healthy", (
        "SOURCE_HEALTH_RECOVERY_CROSS_SOURCE_CONTAMINATION: recovering one source must not rewrite "
        "another source's current or audit state"
    )
    assert control["consecutive_failures"] == 0
    assert control["last_failed"] is None
    assert control["last_error"] is None
    assert control["last_success"] == control_initial.isoformat()
    assert control["last_found"] == 11
    assert control["last_new_items"] == 4
