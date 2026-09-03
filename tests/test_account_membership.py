import sqlite3
from types import SimpleNamespace

import pytest

from account_membership import (
    MembershipAuthorityError,
    install_membership_schema,
    resolve_membership,
)
from auth_context import _provider_membership


def _membership_db(tmp_path):
    path = tmp_path / "memberships.db"
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
    return path


def test_two_authenticated_subjects_resolve_same_company_tenant(tmp_path):
    path = _membership_db(tmp_path)
    a = resolve_membership(str(path), "user-a")
    b = resolve_membership(str(path), "user-b")
    assert a.account_id == "company-a"
    assert b.account_id == "company-a"
    assert a.subject != b.subject
    assert a.role == "admin"
    assert b.role == "member"


def test_cross_company_subject_resolves_only_its_authorized_tenant(tmp_path):
    path = _membership_db(tmp_path)
    c = resolve_membership(str(path), "user-c")
    assert c.account_id == "company-b"
    assert c.account_id != resolve_membership(str(path), "user-a").account_id


def test_revoked_membership_fails_closed_deterministically(tmp_path):
    path = _membership_db(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE account_memberships SET active=0 WHERE subject='user-b'")
    conn.commit()
    conn.close()
    with pytest.raises(MembershipAuthorityError, match="active account membership required"):
        resolve_membership(str(path), "user-b")


def test_missing_membership_authority_fails_closed(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(MembershipAuthorityError, match="unavailable"):
        resolve_membership(str(missing), "user-a")


def test_provider_database_mode_uses_server_membership_not_jwt_account(monkeypatch, tmp_path):
    path = _membership_db(tmp_path)
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE", "database")
    monkeypatch.setenv("OBRASIGNAL_MEMBERSHIP_DB", str(path))
    verified = SimpleNamespace(account_id="user-a", subject="user-a")
    account_id, role = _provider_membership(verified)
    assert account_id == "company-a"
    assert role == "admin"


def test_provider_subject_mode_preserves_existing_single_user_behavior(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE", "subject")
    verified = SimpleNamespace(account_id="user-a", subject="user-a")
    account_id, role = _provider_membership(verified)
    assert account_id == "user-a"
    assert role is None


def test_invalid_membership_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE", "header")
    verified = SimpleNamespace(account_id="user-a", subject="user-a")
    with pytest.raises(RuntimeError, match="Invalid OBRASIGNAL_ACCOUNT_MEMBERSHIP_MODE"):
        _provider_membership(verified)
