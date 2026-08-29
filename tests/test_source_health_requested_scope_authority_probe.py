"""Contracts probe: requested-source Source Health must carry explicit scope authority."""
from datetime import datetime, timezone
import sqlite3


def test_requested_source_contract_does_not_keep_global_looking_scope_labels():
    from source_health import source_health_contract

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        contract = source_health_contract(
            conn,
            sources=["TED"],
            now=datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc),
        )

        assert [item["source"] for item in contract["items"]] == ["TED"]

        # A subset contract must be self-describing. Otherwise consumers can read
        # requested-source currentness as if it were global registered/active
        # coverage authority. Preserve UNKNOWN rather than hiding the scope change.
        assert contract.get("scope") != "registered_sources", (
            "REQUESTED_SOURCE_SCOPE_AMBIGUOUS: subset items retain the global-looking "
            "scope=registered_sources label"
        )
        assert contract.get("coverage_scope") != "active_sources", (
            "REQUESTED_SOURCE_COVERAGE_SCOPE_AMBIGUOUS: subset summary retains the "
            "global-looking coverage_scope=active_sources label"
        )
        assert contract.get("requested_sources") == ["TED"], (
            "REQUESTED_SOURCE_SCOPE_NOT_RECONSTRUCTABLE: the contract does not carry "
            "the requested source set"
        )
    finally:
        conn.close()
