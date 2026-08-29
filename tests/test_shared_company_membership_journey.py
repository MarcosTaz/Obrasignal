import sqlite3
from types import SimpleNamespace

import pytest

from account_membership import MembershipAuthorityError, install_membership_schema, resolve_membership
from auth_context import _provider_membership
from company_profile import load_profile, save_profile
from opportunity_workflow import get_workflow, set_workflow


def _seed_memberships(path):
    conn = sqlite3.connect(path)
    install_membership_schema(conn)
    conn.executemany(
        "INSERT INTO account_memberships(subject, account_id, role, active) VALUES(?,?,?,1)",
        [
            ("user-a", "company-a", "admin"),
            ("user-b", "company-a", "member"),
            ("user-c", "company-b", "admin"),
        ],
    )
    conn.commit()
    conn.close()


def _identity(subject):
    return SimpleNamespace(account_id=subject, subject=subject)


def test_user_a_write_is_visible_to_user_b_but_not_user_c_after_return(monkeypatch, tmp_path):
    database = tmp_path / "shared-company.db"
    _seed_memberships(database)
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE", "database")
    monkeypatch.setenv("OBRASIGNAL_MEMBERSHIP_DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))

    account_a, role_a = _provider_membership(_identity("user-a"))
    account_b, role_b = _provider_membership(_identity("user-b"))
    account_c, role_c = _provider_membership(_identity("user-c"))

    assert (account_a, role_a) == ("company-a", "admin")
    assert (account_b, role_b) == ("company-a", "member")
    assert (account_c, role_c) == ("company-b", "admin")

    saved = save_profile(
        {
            "name": "Shared Company A",
            "activity": "estruturas metálicas",
            "coverage_mode": "portugal",
            "countries": ["PRT"],
            "cpv_prefixes": ["4522", "443"],
        },
        account_id=account_a,
    )
    assert saved["account_id"] == "company-a"

    returned_b = resolve_membership(str(database), "user-b")
    seen_by_b = load_profile(returned_b.account_id)
    seen_by_c = load_profile(account_c)

    assert returned_b.account_id == "company-a"
    assert seen_by_b["name"] == "Shared Company A"
    assert seen_by_b["activity"] == "estruturas metálicas"
    assert seen_by_c["account_id"] == "company-b"
    assert seen_by_c["name"] != "Shared Company A"


def test_same_company_workflow_handoff_is_shared_cross_company_isolated(tmp_path):
    database = tmp_path / "shared-workflow.db"
    _seed_memberships(database)
    a = resolve_membership(str(database), "user-a")
    b = resolve_membership(str(database), "user-b")
    c = resolve_membership(str(database), "user-c")

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        written = set_workflow(conn, a.account_id, "TED", "2026/S-shared", "REVIEWING", "A iniciou revisão")
        seen_by_b = get_workflow(conn, b.account_id, "TED", "2026/S-shared")
        seen_by_c = get_workflow(conn, c.account_id, "TED", "2026/S-shared")
    finally:
        conn.close()

    assert written["status"] == "REVIEWING"
    assert seen_by_b["status"] == "REVIEWING"
    assert seen_by_b["note"] == "A iniciou revisão"
    assert seen_by_c["status"] == "NEW"
    assert seen_by_c["note"] is None


def test_roles_have_explicit_different_write_permissions(tmp_path):
    database = tmp_path / "roles.db"
    _seed_memberships(database)
    admin = resolve_membership(str(database), "user-a")
    member = resolve_membership(str(database), "user-b")

    assert admin.allows("profile:write") is True
    assert member.allows("profile:write") is False
    assert admin.allows("workflow:write") is True
    assert member.allows("workflow:write") is True
    assert admin.allows("membership:manage") is True
    assert member.allows("membership:manage") is False


def test_revocation_blocks_return_before_company_state_can_be_resolved(monkeypatch, tmp_path):
    database = tmp_path / "revoked-company.db"
    _seed_memberships(database)
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE", "database")
    monkeypatch.setenv("OBRASIGNAL_MEMBERSHIP_DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))

    assert _provider_membership(_identity("user-b"))[0] == "company-a"
    conn = sqlite3.connect(database)
    conn.execute("UPDATE account_memberships SET active=0 WHERE subject='user-b'")
    conn.commit()
    conn.close()

    with pytest.raises(MembershipAuthorityError, match="active account membership required"):
        _provider_membership(_identity("user-b"))


def test_actor_identity_remains_distinct_from_shared_business_tenant(monkeypatch, tmp_path):
    database = tmp_path / "actor-company.db"
    _seed_memberships(database)
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE", "database")
    monkeypatch.setenv("OBRASIGNAL_MEMBERSHIP_DB", str(database))

    a = resolve_membership(str(database), "user-a")
    b = resolve_membership(str(database), "user-b")
    assert a.account_id == b.account_id == "company-a"
    assert a.subject == "user-a"
    assert b.subject == "user-b"
    assert a.subject != b.subject
