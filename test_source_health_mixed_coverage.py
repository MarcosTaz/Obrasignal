"""Data-truth probe: mixed source states must aggregate coverage from active sources only."""
from datetime import datetime, timezone
import sqlite3

from source_health import (
    ensure_source_health,
    record_source_projection_failure,
    record_source_result,
    source_health_contract,
)


ACTIVE_FAILING = "TED"
ACTIVE_CONTROL = "BASE"
READY_NON_COVERAGE = "SERVICE_BUND_DE"


def _contract(conn, *, now):
    return source_health_contract(
        conn,
        sources=[ACTIVE_FAILING, ACTIVE_CONTROL, READY_NON_COVERAGE],
        now=now,
    )


def test_mixed_source_summary_uses_only_active_coverage_and_recovers_cleanly():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)

    stale_success = datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc)
    current_success = datetime(2026, 8, 29, 4, 0, tzinfo=timezone.utc)
    failures = [
        datetime(2026, 8, 29, 4, 5, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 4, 10, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 4, 15, tzinfo=timezone.utc),
    ]

    record_source_result(
        conn,
        ACTIVE_FAILING,
        success=True,
        duration_ms=10,
        found=7,
        new_items=2,
        observed_at=stale_success,
    )
    record_source_result(
        conn,
        ACTIVE_CONTROL,
        success=True,
        duration_ms=11,
        found=13,
        new_items=3,
        observed_at=current_success,
    )
    record_source_result(
        conn,
        READY_NON_COVERAGE,
        success=True,
        duration_ms=9,
        found=5,
        new_items=1,
        observed_at=stale_success,
    )

    for index, failed_at in enumerate(failures, start=1):
        record_source_projection_failure(
            conn,
            ACTIVE_FAILING,
            error=sqlite3.OperationalError(f"synthetic active failure {index}"),
            observed_at=failed_at,
        )
        record_source_projection_failure(
            conn,
            READY_NON_COVERAGE,
            error=sqlite3.OperationalError(f"synthetic ready failure {index}"),
            observed_at=failed_at,
        )

    degraded = _contract(
        conn,
        now=datetime(2026, 8, 29, 4, 16, tzinfo=timezone.utc),
    )
    items = {item["source"]: item for item in degraded["items"]}

    assert items[ACTIVE_FAILING]["coverage_expected"] is True
    assert items[ACTIVE_FAILING]["health"] == "unavailable"
    assert items[ACTIVE_CONTROL]["coverage_expected"] is True
    assert items[ACTIVE_CONTROL]["health"] == "healthy"
    assert items[READY_NON_COVERAGE]["coverage_expected"] is False
    assert items[READY_NON_COVERAGE]["health"] == "unavailable"

    summary = degraded["summary"]
    assert summary["expected_source_count"] == 2
    assert summary["observed_expected_source_count"] == 2
    assert summary["coverage_status"] == "unavailable", (
        "SOURCE_HEALTH_SUMMARY_AUTHORITY_DRIFT: an unavailable active source must dominate mixed active coverage"
    )
    assert summary["all_expected_sources_current"] is False
    assert summary["market_absence_proven"] is False
    assert summary["zero_market_claim_allowed"] is False

    recovered_at = datetime(2026, 8, 29, 4, 20, tzinfo=timezone.utc)
    record_source_result(
        conn,
        ACTIVE_FAILING,
        success=True,
        duration_ms=12,
        found=8,
        new_items=1,
        observed_at=recovered_at,
    )

    recovered = _contract(
        conn,
        now=datetime(2026, 8, 29, 4, 21, tzinfo=timezone.utc),
    )
    recovered_items = {item["source"]: item for item in recovered["items"]}
    recovered_summary = recovered["summary"]

    assert recovered_items[ACTIVE_FAILING]["health"] == "healthy"
    assert recovered_items[ACTIVE_CONTROL]["health"] == "healthy"
    assert recovered_items[READY_NON_COVERAGE]["health"] == "unavailable"
    assert recovered_summary["expected_source_count"] == 2
    assert recovered_summary["observed_expected_source_count"] == 2
    assert recovered_summary["coverage_status"] == "current", (
        "SOURCE_HEALTH_READY_SOURCE_COVERAGE_CONTAMINATION: a ready/non-active source must not block active coverage recovery"
    )
    assert recovered_summary["all_expected_sources_current"] is True
    assert recovered_summary["market_absence_proven"] is False
    assert recovered_summary["zero_market_claim_allowed"] is False
