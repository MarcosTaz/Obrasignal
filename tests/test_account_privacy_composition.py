import sqlite3

import pytest

from account_privacy_composition import (
    AccountPrivacyCompositionError,
    account_privacy_composition_inventory,
    assert_composed_operation_complete,
    operation_blockers,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_known_transitive_push_delivery_is_discovered_without_account_id():
    conn = _conn()
    conn.execute(
        """CREATE TABLE opportunity_events(
            id INTEGER PRIMARY KEY,
            account_id TEXT NOT NULL,
            event_key TEXT,
            event_type TEXT,
            created_at TEXT,
            delivered_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE push_devices(
            id INTEGER PRIMARY KEY,
            account_id TEXT NOT NULL,
            installation_id TEXT,
            expo_push_token TEXT,
            platform TEXT,
            binding_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            last_error TEXT,
            revoked_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE push_deliveries(
            id INTEGER PRIMARY KEY,
            event_id INTEGER NOT NULL,
            push_device_id INTEGER NOT NULL,
            ticket_id TEXT,
            submitted_at TEXT,
            last_error TEXT,
            attempt_count INTEGER,
            last_attempt_at TEXT,
            next_attempt_at TEXT,
            expo_push_token TEXT,
            receipt_status TEXT,
            receipt_checked_at TEXT,
            receipt_error TEXT,
            failed_at TEXT
        )"""
    )

    inventory = account_privacy_composition_inventory(conn)
    assert "push_deliveries" not in inventory["direct_account_tables"]
    assert inventory["known_transitive_private_tables"] == ["push_deliveries"]

    deletion = {item["table"]: item for item in operation_blockers(conn, "deletion")}
    assert deletion["push_deliveries"]["reason"] == "UNKNOWN_OWNER_CONTRACT"
    assert "opportunity_events.id -> account_id" in deletion["push_deliveries"]["tenant_path"]

    with pytest.raises(
        AccountPrivacyCompositionError,
        match="account_deletion_composition_incomplete:push_deliveries,push_devices",
    ):
        assert_composed_operation_complete(conn, "deletion")


def test_unclassified_future_direct_account_table_fails_closed():
    conn = _conn()
    conn.execute(
        "CREATE TABLE future_private_state(id INTEGER PRIMARY KEY, account_id TEXT, secret TEXT)"
    )

    blockers = operation_blockers(conn, "export")
    assert blockers == [
        {
            "table": "future_private_state",
            "reason": "UNCLASSIFIED_DIRECT_ACCOUNT_DATA",
            "owner": "UNKNOWN",
        }
    ]
    with pytest.raises(AccountPrivacyCompositionError):
        assert_composed_operation_complete(conn, "export")


def test_test_fixture_table_in_primary_store_is_a_privacy_boundary_violation():
    conn = _conn()
    conn.execute(
        """CREATE TABLE e2e_opportunity_fixtures(
            fixture_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            run_id TEXT NOT NULL
        )"""
    )

    blockers = operation_blockers(conn, "deletion")
    assert blockers == [
        {
            "table": "e2e_opportunity_fixtures",
            "reason": "STORE_BOUNDARY_VIOLATION",
            "owner": "E2E fixture / #335",
        }
    ]


def test_canonical_current_private_tables_have_no_new_composition_blocker():
    conn = _conn()
    for table in (
        "accounts",
        "company_profiles",
        "opportunity_decisions",
        "opportunity_events",
        "opportunity_workflow",
        "evaluation_events",
    ):
        conn.execute(f'CREATE TABLE "{table}"(id INTEGER PRIMARY KEY, account_id TEXT)')

    assert operation_blockers(conn, "export") == []
    assert operation_blockers(conn, "deletion") == []
    assert_composed_operation_complete(conn, "export")
    assert_composed_operation_complete(conn, "deletion")


def test_prebuild_company_state_is_explicit_unknown_not_silent_complete():
    conn = _conn()
    conn.execute(
        """CREATE TABLE company_state_snapshots(
            id INTEGER PRIMARY KEY,
            account_id TEXT NOT NULL,
            state_version TEXT
        )"""
    )

    blockers = operation_blockers(conn, "export")
    assert blockers == [
        {
            "table": "company_state_snapshots",
            "reason": "UNKNOWN_OWNER_CONTRACT",
            "owner": "Company State / company_state_store",
            "tenant_path": "company_state_snapshots.account_id",
        }
    ]
