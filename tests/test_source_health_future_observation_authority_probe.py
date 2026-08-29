"""Data-truth probe: future source observations must fail closed for coverage authority."""
from datetime import datetime, timedelta, timezone
import sqlite3


def test_future_success_observation_cannot_make_active_coverage_current():
    from source_health import record_source_result, source_health_contract
    from source_registry import SOURCES

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    now = datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc)
    try:
        active_sources = sorted(
            source for source, meta in SOURCES.items() if meta.get("status") == "active"
        )
        assert "TED" in active_sources

        for source in active_sources:
            observed_at = now + timedelta(minutes=5) if source == "TED" else now - timedelta(minutes=5)
            record_source_result(
                conn,
                source,
                success=True,
                duration_ms=10,
                found=0,
                new_items=0,
                observed_at=observed_at,
            )

        contract = source_health_contract(conn, now=now)
        ted = next(item for item in contract["items"] if item["source"] == "TED")

        assert ted["freshness"] == "unknown"
        assert ted["health"] == "unknown"
        assert ted["stats_state"] == "unknown"
        assert "future_timestamp" in ted["reason_codes"]
        assert contract["summary"]["coverage_status"] == "unknown"
        assert contract["summary"]["all_expected_sources_current"] is False
        assert contract["summary"]["market_absence_proven"] is False
        assert contract["summary"]["zero_market_claim_allowed"] is False
    finally:
        conn.close()
