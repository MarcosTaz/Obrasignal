"""Authorization failing-before for missing auth-mode fail-open semantics.

This probe does not define Auth policy. It proves only the authorization invariant
that an absent auth-mode configuration must not create a request identity that can
reach a private write side effect in a production-capable API boundary.
"""

import sqlite3

import api


def test_missing_auth_mode_cannot_reach_private_profile_write(monkeypatch, tmp_path):
    db_path = tmp_path / "authz-missing-mode.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(api, "bootstrap_account", lambda _account_id: 0)

    response = api.APP.test_client().post(
        "/api/v1/profile",
        json={"name": "must-not-persist"},
    )

    # Missing security authority must deny before any private write/account
    # bootstrap side effect. Response wording is secondary to zero mutation.
    assert response.status_code in {401, 403, 503}

    if not db_path.exists():
        return

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "accounts" in tables:
            assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
        if "company_profiles" in tables:
            assert conn.execute("SELECT COUNT(*) FROM company_profiles").fetchone()[0] == 0
    finally:
        conn.close()
