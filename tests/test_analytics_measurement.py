import sqlite3

from analytics_measurement import (
    MISSING,
    OBSERVABLE,
    PARTIAL,
    UNKNOWN,
    account_milestones,
    duration_seconds,
    event_taxonomy,
    instrumentation_debt,
    validate_event_taxonomy,
)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE accounts(
            account_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            evaluation_activated_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE company_profiles(
            account_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE evaluation_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            metadata_json TEXT,
            UNIQUE(account_id,event_name,occurred_at)
        )"""
    )
    return conn


def test_taxonomy_requires_measurement_quality_contract():
    assert validate_event_taxonomy() is True
    taxonomy = event_taxonomy()
    for contract in taxonomy.values():
        assert contract["tenant_boundary"]
        assert contract["timestamp_semantics"]
        assert contract["dedupe"]
        assert contract["missing_behavior"]


def test_system_decision_log_is_not_customer_decision_telemetry():
    customer_decision = event_taxonomy()["customer_decision"]
    assert customer_decision["status"] == MISSING
    assert customer_decision["source"] is None
    assert "opportunity_decisions" in customer_decision["missing_behavior"]


def test_missing_event_is_unknown_not_zero():
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            ("company-a", "2026-08-25T10:00:00+00:00"),
        )
        milestones = account_milestones(conn, "company-a")
        assert milestones["market_readiness"]["quality"] == UNKNOWN
        assert milestones["market_readiness"]["occurred_at"] is None
        assert milestones["first_shortlist"]["quality"] == UNKNOWN
        assert milestones["conversion"]["quality"] == UNKNOWN
    finally:
        conn.close()


def test_profile_snapshot_without_event_does_not_invent_first_completion_time():
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            ("company-a", "2026-08-25T10:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            ("company-a", "{}", "2026-08-25T12:00:00+00:00"),
        )
        milestones = account_milestones(conn, "company-a")
        profile = milestones["profile_completion"]
        assert profile["quality"] == PARTIAL
        assert profile["occurred_at"] is None
        assert profile["latest_persisted_at"] == "2026-08-25T12:00:00+00:00"
        assert "first completion event is not proven" in profile["reason"]
    finally:
        conn.close()


def test_event_milestones_are_strictly_tenant_scoped():
    conn = _db()
    try:
        conn.executemany(
            "INSERT INTO accounts(account_id,created_at) VALUES(?,?)",
            [
                ("company-a", "2026-08-25T10:00:00+00:00"),
                ("company-b", "2026-08-25T10:00:00+00:00"),
            ],
        )
        conn.execute(
            "INSERT INTO evaluation_events(account_id,event_name,occurred_at) VALUES(?,?,?)",
            ("company-b", "first_shortlist_generated", "2026-08-25T11:00:00+00:00"),
        )
        a = account_milestones(conn, "company-a")
        b = account_milestones(conn, "company-b")
        assert a["first_shortlist"]["quality"] == UNKNOWN
        assert b["first_shortlist"]["quality"] == OBSERVABLE
        assert b["first_shortlist"]["occurred_at"] == "2026-08-25T11:00:00+00:00"
    finally:
        conn.close()


def test_workflow_current_state_is_not_claimed_as_transition_history():
    workflow = event_taxonomy()["workflow_action"]
    assert workflow["status"] == PARTIAL
    assert "latest state update only" in workflow["timestamp_semantics"]
    assert "current row is not an event history" in workflow["missing_behavior"]


def test_duration_never_turns_missing_or_invalid_time_into_zero():
    assert duration_seconds(None, "2026-08-25T11:00:00+00:00") == {
        "quality": UNKNOWN,
        "seconds": None,
        "reason": "missing_endpoint",
    }
    assert duration_seconds(
        "2026-08-25T12:00:00+00:00", "2026-08-25T11:00:00+00:00"
    ) == {"quality": UNKNOWN, "seconds": None, "reason": "end_before_start"}
    assert duration_seconds(
        "2026-08-25T10:00:00+00:00", "2026-08-25T10:02:00+00:00"
    ) == {"quality": OBSERVABLE, "seconds": 120, "reason": None}


def test_instrumentation_debt_contains_only_decision_blocking_gaps():
    debt = instrumentation_debt()
    assert debt
    assert all(item["decision_blocked"] for item in debt)
    assert [item["priority"] for item in debt[:2]] == ["P0", "P0"]
