from flask import Flask

from earnedcash.web import create_earnedcash_blueprint


def client(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-dashboard")
    app = Flask(__name__)
    app.register_blueprint(create_earnedcash_blueprint())
    app.testing = True
    return app.test_client()


def test_dashboard_sample_does_not_self_attest_verified_or_due_truth(monkeypatch):
    response = client(monkeypatch).get("/api/v1/earnedcash/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"verified":true' not in body
    assert '"due":true' not in body
    assert "Tenant, evidence verification and due-state are server/operator-controlled" in body
    assert "Correct £0 is a pass." in body


def test_dashboard_sample_is_accepted_as_raw_fail_closed_input(monkeypatch):
    rows = [
        {"record_id":"a1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"APPLICATION","amount":"100"},
        {"record_id":"c1x","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"CERTIFICATE","amount":"100","relates_to":"a1"},
        {"record_id":"i1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"INVOICE","amount":"100","relates_to":"c1x"},
    ]
    response = client(monkeypatch).post(
        "/api/v1/earnedcash/reconcile-ledger", json={"records": rows}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["verified_cash"] == "0"
    assert data["due_unpaid"] == "0"
    assert data["unknown_value"] == "100"
    assert data["recovery_queue"] == []
