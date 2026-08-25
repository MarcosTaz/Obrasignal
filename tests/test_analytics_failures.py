import sqlite3

from analytics_failures import (
    failure_registry,
    source_failure_snapshot,
    validate_failure_registry,
)


def test_failure_registry_never_turns_unmeasured_failure_into_healthy():
    assert validate_failure_registry() is True
    registry = failure_registry()
    assert registry["billing_verification_failure"]["measurement_status"] == "MISSING"
    assert "UNKNOWN" in registry["billing_verification_failure"]["missing_behavior"]
    assert registry["notification_failure"]["measurement_status"] == "MISSING"
    assert registry["auth_failure"]["measurement_status"] == "PARTIAL"


def test_failure_registry_privacy_contract_forbids_secret_payloads():
    registry = failure_registry()
    assert "token material forbidden" in registry["auth_failure"]["privacy"]
    assert "no device token" in registry["notification_failure"]["privacy"]
    assert "no receipt/token/secret" in registry["billing_verification_failure"]["privacy"]


def test_missing_source_health_table_is_unknown_not_healthy():
    conn = sqlite3.connect(":memory:")
    try:
        snapshot = source_failure_snapshot(conn)
        assert snapshot["quality"] == "UNKNOWN"
        assert snapshot["sources"] == []
        assert snapshot["reason"] == "source_health_table_missing"
    finally:
        conn.close()


def test_empty_source_health_is_unknown_not_zero_failures():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """CREATE TABLE source_health(
                source TEXT PRIMARY KEY,
                last_attempt TEXT,
                last_success TEXT,
                last_error TEXT,
                status TEXT
            )"""
        )
        snapshot = source_failure_snapshot(conn)
        assert snapshot["quality"] == "UNKNOWN"
        assert "absence is not healthy" in snapshot["reason"]
    finally:
        conn.close()


def test_source_failure_snapshot_redacts_raw_error_text():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """CREATE TABLE source_health(
                source TEXT PRIMARY KEY,
                last_attempt TEXT,
                last_success TEXT,
                last_error TEXT,
                status TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO source_health VALUES(?,?,?,?,?)",
            ("TED", "2026-08-25T10:00:00+00:00", None, "sensitive raw provider error", "degraded"),
        )
        snapshot = source_failure_snapshot(conn)
        assert snapshot["quality"] == "OBSERVABLE"
        assert snapshot["sources"] == [{
            "source": "TED",
            "status": "degraded",
            "last_attempt": "2026-08-25T10:00:00+00:00",
            "last_success": None,
            "error_present": True,
        }]
        assert "sensitive raw provider error" not in str(snapshot)
    finally:
        conn.close()
