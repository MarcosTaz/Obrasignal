from storage_contract import (
    KNOWN_TABLE_OWNERS,
    PREBUILD_CONTRACTS,
    REGISTERED_ADDITIVE_MIGRATIONS,
    STARTUP_CONTRACTS,
    tenant_owned_tables,
)


def test_watchlist_additive_persistence_is_registered_on_single_owner_registry():
    workflow = STARTUP_CONTRACTS["opportunity_workflow"]
    assert {"priority", "saved_at"}.issubset(workflow.required_columns)
    assert {
        "idx_opportunity_workflow_account_saved",
        "idx_opportunity_workflow_account_status_priority",
    }.issubset(workflow.required_indexes)
    assert REGISTERED_ADDITIVE_MIGRATIONS["opportunity_workflow"] == ("priority", "saved_at")
    assert KNOWN_TABLE_OWNERS["opportunity_workflow"] is workflow


def test_pursuit_workspace_family_is_explicit_prebuild_not_startup():
    expected = {
        "pursuit_workspaces",
        "pursuit_workspace_blockers",
        "pursuit_workspace_notes",
        "pursuit_workspace_questions",
    }
    assert expected.issubset(PREBUILD_CONTRACTS)
    assert expected.issubset(KNOWN_TABLE_OWNERS)
    assert expected.isdisjoint(STARTUP_CONTRACTS)

    workspace = PREBUILD_CONTRACTS["pursuit_workspaces"]
    assert workspace.tenant_column == "account_id"
    assert ("account_id", "opportunity_id") in workspace.unique_keys
    assert "idx_pursuit_workspace_account" in workspace.required_indexes
    assert "idx_pursuit_blocker_workspace" in PREBUILD_CONTRACTS["pursuit_workspace_blockers"].required_indexes
    assert "idx_pursuit_note_workspace" in PREBUILD_CONTRACTS["pursuit_workspace_notes"].required_indexes
    assert "idx_pursuit_question_workspace" in PREBUILD_CONTRACTS["pursuit_workspace_questions"].required_indexes

    assert "pursuit_workspaces" not in tenant_owned_tables()
    assert tenant_owned_tables(include_prebuild=True)["pursuit_workspaces"] == "account_id"
