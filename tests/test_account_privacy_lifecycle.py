import json
import sqlite3
from types import SimpleNamespace

import pytest
from flask import Flask

import account_privacy
from account_privacy import (
    AccountDataContractError,
    DELETE_CONFIRMATION,
    account_data_inventory,
    export_account_data,
    request_account_deletion,
)
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


def _seed(path):
    conn = _open(path)
    ensure_account(conn, "tenant-a")
    ensure_account(conn, "tenant-b")
    ensure_profile_table(conn)
    ensure_decision_table(conn)
    ensure_event_table(conn)
    ensure_workflow_table(conn)
    ensure_evaluation_schema(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT)"
    )
    conn.execute(
        "INSERT OR REPLACE INTO tenders(id,source,external_id,title) VALUES(1,'PUBLIC','P-1','Shared public fact')"
    )

    now = "2026-08-25T18:00:00+00:00"
    for tenant, marker in (("tenant-a", "A-PRIVATE"), ("tenant-b", "B-PRIVATE")):
        conn.execute(
            "INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            (tenant, json.dumps({"account_id": tenant, "name": marker, "activity": "works"}), now),
        )
        conn.execute(
            """INSERT INTO opportunity_decisions
               (account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (tenant, "PUBLIC", "P-1", "REVIEW", marker, 70, json.dumps({"marker": marker}), "test", now),
        )
        conn.execute(
            """INSERT INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at,delivered_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (tenant, f"{tenant}:P-1", 1, "PUBLIC", "new_high_match", 80, now, None),
        )
        conn.execute(
            """INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at)
               VALUES(?,?,?,?,?,?)""",
            (tenant, "PUBLIC", "P-1", "REVIEWING", marker, now),
        )
        conn.execute(
            """INSERT INTO evaluation_events(account_id,event_name,occurred_at,metadata_json)
               VALUES(?,?,?,?)""",
            (tenant, "profile_ready", now, json.dumps({"marker": marker})),
        )
    conn.execute(
        """UPDATE accounts SET plan='pro', subscription_status='active', store='test-store',
           product_id='product-a', original_transaction_id='tx-a', billing_synced_at=?
           WHERE account_id='tenant-a'""",
        (now,),
    )
    conn.commit()
    return conn


def test_inventory_matches_every_current_account_scoped_owner(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    inventory = account_data_inventory(conn)
    assert inventory["missing"] == []
    assert inventory["unknown"] == []
    assert inventory["unknown_account_columns"] == []
    assert inventory["discovered"] == sorted(account_privacy.ACCOUNT_SCOPED_TABLES)
    conn.close()


def test_export_is_authenticated_tenant_payload_not_cross_tenant_dump(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    payload = export_account_data(conn, "tenant-a")
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["schema_version"] == "account-export.v1"
    assert payload["account"]["account_id"] == "tenant-a"
    assert payload["company_profile"]["profile"]["name"] == "A-PRIVATE"
    assert payload["opportunity_decisions"][0]["features"] == {"marker": "A-PRIVATE"}
    assert payload["evaluation_events"][0]["metadata"] == {"marker": "A-PRIVATE"}
    assert "B-PRIVATE" not in encoded
    assert "tenant-b" not in encoded
    assert payload["scope"]["shared_public_procurement_data_included"] is False
    assert payload["scope"]["identity_provider_data_included"] is False
    assert payload["scope"]["device_local_private_cache_included"] is False
    conn.close()


def test_export_fails_closed_when_future_account_owned_table_is_unregistered(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    conn.execute("CREATE TABLE future_private_state(account_id TEXT NOT NULL, secret TEXT)")
    conn.execute("INSERT INTO future_private_state VALUES('tenant-a','future-secret')")
    conn.commit()

    with pytest.raises(AccountDataContractError, match="account_data_contract_incomplete"):
        export_account_data(conn, "tenant-a")
    conn.close()


def test_deletion_removes_only_requesting_tenant_private_rows_and_preserves_public_truth(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    tenant_b_before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id='tenant-b'").fetchone()[0]
        for table in account_privacy.DEPENDENT_PRIVATE_TABLES
    }

    state = request_account_deletion(conn, "tenant-a")

    assert state["state"] == "PENDING"
    assert state["product_private_db_deleted"] is True
    assert state["external_revocation"] == "PENDING"
    assert state["server_cleanup"]["shared_public_procurement_deleted"] is False
    assert state["server_cleanup"]["minimal_account_tombstone_retained"] is True
    assert "AUTH_PROVIDER_IDENTITY_AND_SESSION_REVOCATION" in state["pending_boundaries"]

    for table in account_privacy.DEPENDENT_PRIVATE_TABLES:
        assert conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE account_id='tenant-a'"
        ).fetchone()[0] == 0
        assert conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE account_id='tenant-b'"
        ).fetchone()[0] == tenant_b_before[table]

    assert conn.execute("SELECT COUNT(*) FROM tenders WHERE id=1").fetchone()[0] == 1
    deleted = dict(conn.execute("SELECT * FROM accounts WHERE account_id='tenant-a'").fetchone())
    survivor = dict(conn.execute("SELECT * FROM accounts WHERE account_id='tenant-b'").fetchone())
    assert deleted["status"] == "deleted_pending_revocation"
    assert deleted["plan"] == "expired"
    assert deleted["subscription_status"] == "none"
    assert deleted["store"] is None
    assert deleted["product_id"] is None
    assert deleted["original_transaction_id"] is None
    assert survivor["status"] == "active"
    conn.close()


def test_deletion_contract_failure_is_failed_not_success_and_keeps_data(tmp_path):
    conn = _seed(tmp_path / "privacy.db")
    conn.execute("CREATE TABLE future_private_state(account_id TEXT NOT NULL, secret TEXT)")
    conn.execute("INSERT INTO future_private_state VALUES('tenant-a','future-secret')")
    conn.commit()

    with pytest.raises(AccountDataContractError):
        request_account_deletion(conn, "tenant-a")

    assert conn.execute(
        "SELECT status FROM accounts WHERE account_id='tenant-a'"
    ).fetchone()[0] == "deletion_failed"
    assert conn.execute(
        "SELECT COUNT(*) FROM company_profiles WHERE account_id='tenant-a'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM future_private_state WHERE account_id='tenant-a'"
    ).fetchone()[0] == 1
    conn.close()


def test_http_export_requires_auth_and_deletion_requires_explicit_confirmation(tmp_path, monkeypatch):
    path = tmp_path / "privacy.db"
    _seed(path).close()
    app = Flask(__name__)
    app.register_blueprint(account_privacy.bp)
    monkeypatch.setattr(account_privacy, "_db", lambda: _open(path))

    def no_identity():
        raise RuntimeError("no auth")

    monkeypatch.setattr(account_privacy, "configured_identity", no_identity)
    client = app.test_client()
    assert client.get("/api/v1/account/export").status_code == 401

    monkeypatch.setattr(
        account_privacy,
        "configured_identity",
        lambda: SimpleNamespace(account_id="tenant-a", authenticated=True),
    )
    response = client.post("/api/v1/account/deletion", json={"confirmation": "DELETE"})
    assert response.status_code == 400
    with _open(path) as conn:
        assert conn.execute(
            "SELECT status FROM accounts WHERE account_id='tenant-a'"
        ).fetchone()[0] == "active"

    response = client.post(
        "/api/v1/account/deletion",
        json={"confirmation": DELETE_CONFIRMATION},
    )
    assert response.status_code == 202
    assert response.get_json()["state"] == "PENDING"


def test_deletion_state_guard_blocks_ordinary_private_api_after_cleanup(tmp_path, monkeypatch):
    path = tmp_path / "privacy.db"
    conn = _seed(path)
    request_account_deletion(conn, "tenant-a")
    conn.close()

    app = Flask(__name__)
    app.before_request(account_privacy._privacy_lifecycle_guard)

    @app.get("/api/v1/private-probe")
    def private_probe():
        return {"private": "should-not-render"}

    monkeypatch.setattr(account_privacy, "_db", lambda: _open(path))
    monkeypatch.setattr(
        account_privacy,
        "configured_identity",
        lambda: SimpleNamespace(account_id="tenant-a", authenticated=True),
    )
    response = app.test_client().get("/api/v1/private-probe")
    assert response.status_code == 410
    assert response.get_json()["error"] == "account_privacy_lifecycle_block"
