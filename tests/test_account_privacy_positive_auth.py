import json
import sqlite3

from flask import Flask

import account_privacy
from account_privacy import DELETE_CONFIRMATION
from account_registry import ensure_account
from company_profile import ensure_profile_table
from decision_log import ensure_decision_table
from evaluation_policy import ensure_evaluation_schema
from notification_events import ensure_event_table
from opportunity_workflow import ensure_workflow_table


def _open(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_default_account(path):
    conn = _open(path)
    ensure_account(conn, "default")
    ensure_profile_table(conn)
    ensure_decision_table(conn)
    ensure_event_table(conn)
    ensure_workflow_table(conn)
    ensure_evaluation_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
        (
            "default",
            json.dumps({"account_id": "default", "name": "PRIVATE-DEFAULT"}),
            "2026-08-26T18:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()


def _client(path, monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(account_privacy.bp)
    monkeypatch.setattr(account_privacy, "_db", lambda: _open(path))
    return app.test_client()


def test_missing_auth_configuration_cannot_authorize_account_export(tmp_path, monkeypatch):
    path = tmp_path / "privacy-authz.db"
    _seed_default_account(path)
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)

    response = _client(path, monkeypatch).get("/api/v1/account/export")

    assert response.status_code == 401
    assert b"PRIVATE-DEFAULT" not in response.data


def test_missing_auth_configuration_cannot_authorize_account_deletion(tmp_path, monkeypatch):
    path = tmp_path / "privacy-authz.db"
    _seed_default_account(path)
    monkeypatch.delenv("OBRASIGNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("OBRASIGNAL_ACCOUNT_ID", raising=False)

    response = _client(path, monkeypatch).post(
        "/api/v1/account/deletion",
        json={"confirmation": DELETE_CONFIRMATION},
    )

    assert response.status_code == 401
    with _open(path) as conn:
        assert conn.execute(
            "SELECT status FROM accounts WHERE account_id='default'"
        ).fetchone()[0] == "active"
        assert conn.execute(
            "SELECT COUNT(*) FROM company_profiles WHERE account_id='default'"
        ).fetchone()[0] == 1


def test_explicit_authenticated_identity_still_authorizes_privacy_routes(tmp_path, monkeypatch):
    from types import SimpleNamespace

    path = tmp_path / "privacy-authz.db"
    _seed_default_account(path)
    monkeypatch.setattr(
        account_privacy,
        "configured_identity",
        lambda: SimpleNamespace(account_id="default", authenticated=True),
    )

    response = _client(path, monkeypatch).get("/api/v1/account/export")
    assert response.status_code == 200
    assert b"PRIVATE-DEFAULT" in response.data
