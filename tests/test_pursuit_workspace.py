import sqlite3
from datetime import datetime, timezone

import pytest

from pursuit_workspace import (
    ProviderRegistry,
    add_blocker,
    add_note,
    add_question,
    create_workspace,
    resolve_blocker,
    update_workspace,
    workspace_view,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        title TEXT, buyer TEXT, country TEXT, value TEXT, deadline TEXT,
        publication_date TEXT, url TEXT
    )""")
    conn.execute("INSERT INTO tenders VALUES (1,'TED','O-1','School works','City','PRT','100 EUR','2099-01-01','2026-08-25','https://example.test/1')")
    conn.commit()
    return conn


def test_create_is_idempotent_and_does_not_copy_or_mutate_opportunity():
    conn = _conn()
    before = dict(conn.execute("SELECT * FROM tenders WHERE id=1").fetchone())
    first = create_workspace(conn, "a", 1)
    second = create_workspace(conn, "a", 1)
    after = dict(conn.execute("SELECT * FROM tenders WHERE id=1").fetchone())
    assert first["workspace_id"] == second["workspace_id"]
    assert conn.execute("SELECT COUNT(*) FROM pursuit_workspaces").fetchone()[0] == 1
    assert before == after
    assert set(first).isdisjoint({"title", "buyer", "value", "deadline", "source"})


def test_tenant_isolation_for_workspace_notes_and_blockers():
    conn = _conn()
    create_workspace(conn, "company-a", 1)
    create_workspace(conn, "company-b", 1)
    add_note(conn, "company-a", 1, "private A")
    add_blocker(conn, "company-a", 1, "Waiting for quote")
    a = workspace_view(conn, "company-a", 1)
    b = workspace_view(conn, "company-b", 1)
    assert [n["body"] for n in a["notes"]] == ["private A"]
    assert b["notes"] == []
    assert len(a["blockers"]) == 1
    assert b["blockers"] == []


def test_owner_assignment_fails_closed_without_cross_account_user_directory():
    conn = _conn()
    create_workspace(conn, "a", 1)
    own = update_workspace(conn, "a", 1, {"owner_id": "user-a"}, actor_subject="user-a")
    assert own["owner_id"] == "user-a"
    with pytest.raises(PermissionError, match="owner_not_in_account"):
        update_workspace(conn, "a", 1, {"owner_id": "user-b"}, actor_subject="user-a")


def test_close_archive_and_submission_state_do_not_mutate_opportunity_or_decision():
    conn = _conn()
    create_workspace(conn, "a", 1)
    before = dict(conn.execute("SELECT * FROM tenders WHERE id=1").fetchone())
    closed = update_workspace(conn, "a", 1, {"workspace_status": "CLOSED"}, actor_subject=None)
    archived = update_workspace(conn, "a", 1, {"workspace_status": "ARCHIVED", "submission_state": "READY_TO_SUBMIT"}, actor_subject=None)
    assert closed["workspace_status"] == "CLOSED"
    assert archived["workspace_status"] == "ARCHIVED"
    assert dict(conn.execute("SELECT * FROM tenders WHERE id=1").fetchone()) == before
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "opportunity_decisions" not in tables


def test_manual_blocker_resolves_without_deletion():
    conn = _conn()
    create_workspace(conn, "a", 1)
    blocker = add_blocker(conn, "a", 1, "Subcontractor quote")
    resolved = resolve_blocker(conn, "a", 1, blocker["blocker_id"])
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"]
    assert len(workspace_view(conn, "a", 1)["blockers"]) == 1


def test_notes_and_questions_are_bounded_and_stored_as_plain_data():
    conn = _conn()
    create_workspace(conn, "a", 1)
    payload = "<script>alert(1)</script>"
    note = add_note(conn, "a", 1, payload)
    question = add_question(conn, "a", 1, "Is insurance evidence required?", source_ref="notice:42")
    assert note["body"] == payload
    assert question["status"] == "OPEN"
    with pytest.raises(ValueError):
        add_note(conn, "a", 1, "x" * 8001)
    with pytest.raises(ValueError):
        add_blocker(conn, "a", 1, "x" * 301)


def test_missing_optional_modules_are_explicitly_unavailable():
    conn = _conn()
    create_workspace(conn, "a", 1)
    view = workspace_view(conn, "a", 1)
    assert view["sections"]["milestones"] == {"status": "UNAVAILABLE"}
    assert view["sections"]["economics"] == {"status": "UNAVAILABLE"}
    assert "milestones" in view["missing_capabilities"]


def test_provider_available_and_provider_failure_are_isolated():
    class Good:
        def summary(self, *, account_id, opportunity_id):
            return {"next": "2099-01-01", "ref": "milestone:1"}

    class Broken:
        def summary(self, *, account_id, opportunity_id):
            raise RuntimeError("private provider detail")

    conn = _conn()
    create_workspace(conn, "a", 1)
    view = workspace_view(conn, "a", 1, providers=ProviderRegistry({"milestones": Good(), "economics": Broken()}))
    assert view["sections"]["milestones"]["status"] == "AVAILABLE"
    assert view["sections"]["economics"] == {"status": "FAILED"}
    assert view["opportunity"]["external_id"] == "O-1"
    assert view["sections"]["requirements"] == {"status": "UNAVAILABLE"}


def test_invalid_states_and_unknown_opportunity_fail_closed():
    conn = _conn()
    with pytest.raises(LookupError):
        create_workspace(conn, "a", 999)
    create_workspace(conn, "a", 1)
    with pytest.raises(ValueError):
        update_workspace(conn, "a", 1, {"workspace_status": "PURSUE"}, actor_subject=None)
    with pytest.raises(ValueError):
        update_workspace(conn, "a", 1, {"submission_state": "73_PERCENT"}, actor_subject=None)
