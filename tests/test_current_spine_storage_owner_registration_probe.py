"""Failing-before: current product-owner storage must be registered by Persistence #238."""
from pathlib import Path

from storage_contract import KNOWN_TABLE_OWNERS, REGISTERED_ADDITIVE_MIGRATIONS


def test_watchlist_additive_columns_are_registered_with_persistence_owner():
    registered = set(REGISTERED_ADDITIVE_MIGRATIONS.get("opportunity_workflow", ()))
    assert {"priority", "saved_at"}.issubset(registered), (
        "WATCHLIST_PERSISTENCE_GOVERNANCE_GAP: owner ALTER columns are executable but absent "
        "from #238 registered additive migration contract"
    )


def test_pursuit_workspace_tables_are_known_to_persistence_owner_registry():
    text = Path("pursuit_workspace.py").read_text(encoding="utf-8")
    tables = (
        "pursuit_workspaces",
        "pursuit_workspace_blockers",
        "pursuit_workspace_notes",
        "pursuit_workspace_questions",
    )
    for table in tables:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
        assert table in KNOWN_TABLE_OWNERS, (
            f"PURSUIT_WORKSPACE_PERSISTENCE_GOVERNANCE_GAP: {table} has an owner schema "
            "but is not registered in #238 storage ownership truth"
        )
