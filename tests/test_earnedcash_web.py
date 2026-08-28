from flask import Flask

from earnedcash.web import create_earnedcash_blueprint


def client(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-test")
    app = Flask(__name__)
    app.register_blueprint(create_earnedcash_blueprint())
    app.testing = True
    return app.test_client()


def valid_chain():
    return [
        {"record_id":"a1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"APPLICATION","amount":"100","verified":True},
        {"record_id":"c1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"CERTIFICATE","amount":"100","relates_to":"a1","verified":True},
        {"record_id":"i1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"INVOICE","amount":"100","relates_to":"c1","verified":True,"due":True},
    ]


def test_health_exposes_truth_policy_and_server_tenant(monkeypatch):
    response = client(monkeypatch).get("/api/v1/earnedcash/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["tenant_id"] == "tenant-test"
    assert data["truth_policy"] == "FAIL_CLOSED"


def test_web_reconciliation_uses_server_identity_and_returns_evidence_chain(monkeypatch):
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={"records": valid_chain()})
    assert response.status_code == 200
    data = response.get_json()
    assert data["tenant_id"] == "tenant-test"
    assert data["due_unpaid"] == "100"
    assert data["verified_cash"] == "0"
    assert data["positions"][0]["evidence_chain"] == ["a1", "c1", "i1"]


def test_client_cannot_supply_tenant_id(monkeypatch):
    rows = valid_chain(); rows[0]["tenant_id"] = "other"
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={"records": rows})
    assert response.status_code == 400
    assert response.get_json()["error"] == "tenant_id_is_server_controlled"


def test_missing_records_array_is_400(monkeypatch):
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={})
    assert response.status_code == 400


def test_invalid_amount_is_400_not_zero(monkeypatch):
    rows = valid_chain(); rows[2]["amount"] = "not-money"
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={"records": rows})
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid amount"


def test_unverified_chain_returns_unknown_not_due_unpaid(monkeypatch):
    rows = valid_chain(); rows[0]["verified"] = False
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={"records": rows})
    data = response.get_json()
    assert data["due_unpaid"] == "0"
    assert data["unknown_value"] == "100"
