"""Failing-before probe for Pursuit Workspace persistence on the current trust spine.

Acceptance-only. This does not implement the workspace or duplicate Persistence #238.
"""

from pathlib import Path


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def test_pursuit_workspace_owner_module_and_four_table_contract_exist():
    module = Path("pursuit_workspace.py")
    assert module.exists(), "PURSUIT_WORKSPACE_PERSISTENCE_MISSING: owner module absent on current spine"
    text = module.read_text(encoding="utf-8")
    for table in (
        "pursuit_workspaces",
        "pursuit_workspace_blockers",
        "pursuit_workspace_notes",
        "pursuit_workspace_questions",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    assert "UNIQUE(account_id, opportunity_id)" in text


def test_pursuit_workspace_declared_foreign_keys_require_connection_enforcement():
    text = _read("pursuit_workspace.py")
    assert "FOREIGN KEY(opportunity_id) REFERENCES tenders(id)" in text
    assert "FOREIGN KEY(workspace_id) REFERENCES pursuit_workspaces(workspace_id)" in text
    combined = text + "\n" + (_read("app.py") if Path("app.py").exists() else "")
    assert "PRAGMA foreign_keys=ON" in combined or "PRAGMA foreign_keys = ON" in combined, (
        "PERSISTENCE_FK_ENFORCEMENT_UNKNOWN: schema declares FKs but current connection path does not prove SQLite FK enforcement"
    )


def test_pursuit_workspace_indexes_and_account_scope_are_explicit():
    text = _read("pursuit_workspace.py")
    assert "idx_pursuit_workspace_account" in text
    assert "idx_pursuit_blocker_workspace" in text
    assert "idx_pursuit_note_workspace" in text
    assert "idx_pursuit_question_workspace" in text
    assert "WHERE account_id=? AND opportunity_id=?" in text
