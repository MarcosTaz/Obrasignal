from decimal import Decimal

from flask import Flask

from earnedcash.recovery_queue import RecoveryQueueItem
from earnedcash.store import EarnedCashStore
from earnedcash.web import create_earnedcash_blueprint


def client(monkeypatch, store=None):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-test")
    app = Flask(__name__)
    app.register_blueprint(create_earnedcash_blueprint(store))
    app.testing = True
    return app.test_client()


def self_attested_chain():
    return [
        {"record_id":"a1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"APPLICATION","amount":"100","verified":True},
        {"record_id":"c1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"CERTIFICATE","amount":"100","relates_to":"a1","verified":True},
        {"record_id":"i1","customer_id":"c1","project_id":"p1","currency":"GBP","kind":"INVOICE","amount":"100","relates_to":"c1","verified":True,"due":True},
    ]


def client_chain():
    rows = self_attested_chain()
    for row in rows:
        row.pop("verified", None)
        row.pop("due", None)
    return rows


def queue_item():
    return RecoveryQueueItem(
        case_id="invoice:i1",
        category="INVOICED_DUE_UNPAID",
        amount=Decimal("100"),
        currency="GBP",
        confidence="HIGH",
        evidence_quality="HIGH",
        blocker="PAYMENT_DELAY",
        action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
        priority_score=70,
        evidence_chain=("a1", "c1", "i1"),
    )


def seed_pilot(http):
    assert http.post("/api/v1/earnedcash/companies", json={"company_id":"co1","name":"Alpha Electrical"}).status_code == 201
    assert http.post("/api/v1/earnedcash/customers", json={"customer_id":"c1","company_id":"co1","name":"Main Contractor"}).status_code == 201
    assert http.post("/api/v1/earnedcash/projects", json={"project_id":"p1","company_id":"co1","customer_id":"c1","name":"Hospital","currency":"GBP"}).status_code == 201
    assert http.post("/api/v1/earnedcash/contracts", json={"contract_id":"ct1","project_id":"p1","contract_ref":"JCT-001","original_value":"500000"}).status_code == 201


def test_health_exposes_truth_policy_and_server_tenant(monkeypatch):
    response = client(monkeypatch).get("/api/v1/earnedcash/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["tenant_id"] == "tenant-test"
    assert data["truth_policy"] == "FAIL_CLOSED"
    assert data["persistence"] == "NOT_CONFIGURED"
    assert data["cash_verification"] == "SERVER_EVIDENCE_GATED"


def test_web_client_payload_cannot_promote_unknown_to_recovery(monkeypatch):
    response = client(monkeypatch).post(
        "/api/v1/earnedcash/reconcile-ledger", json={"records": client_chain()}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["tenant_id"] == "tenant-test"
    assert data["due_unpaid"] == "0"
    assert data["verified_cash"] == "0"
    assert data["unknown_value"] == "100"
    assert data["recovery_queue"] == []
    assert data["positions"][0]["evidence_chain"] == ["a1", "c1", "i1"]


def test_web_client_cannot_self_attest_verified_truth(monkeypatch):
    response = client(monkeypatch).post(
        "/api/v1/earnedcash/reconcile-ledger",
        json={"records": self_attested_chain()},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "verified_is_server_controlled"


def test_web_client_cannot_self_attest_due_truth(monkeypatch):
    rows = client_chain(); rows[2]["due"] = True
    response = client(monkeypatch).post(
        "/api/v1/earnedcash/reconcile-ledger", json={"records": rows}
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "due_is_server_controlled"


def test_client_cannot_supply_tenant_id(monkeypatch):
    rows = client_chain(); rows[0]["tenant_id"] = "other"
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={"records": rows})
    assert response.status_code == 400
    assert response.get_json()["error"] == "tenant_id_is_server_controlled"


def test_missing_records_array_is_400(monkeypatch):
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={})
    assert response.status_code == 400


def test_invalid_amount_is_400_not_zero(monkeypatch):
    rows = client_chain(); rows[2]["amount"] = "not-money"
    response = client(monkeypatch).post("/api/v1/earnedcash/reconcile-ledger", json={"records": rows})
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid amount"


def test_persistence_endpoints_fail_explicitly_when_store_not_configured(monkeypatch):
    response = client(monkeypatch).post(
        "/api/v1/earnedcash/companies", json={"company_id":"co1","name":"Alpha"}
    )
    assert response.status_code == 503
    assert response.get_json()["error"] == "earnedcash_persistence_not_configured"


def test_persistent_client_reconcile_persists_only_safe_empty_queue(monkeypatch):
    store = EarnedCashStore.memory()
    http = client(monkeypatch, store)
    seed_pilot(http)

    response = http.post(
        "/api/v1/earnedcash/projects/p1/reconcile-ledger",
        json={"records": client_chain()},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["queue_persisted"] is True
    assert data["due_unpaid"] == "0"
    assert data["unknown_value"] == "100"
    assert data["recovery_queue"] == []
    assert http.get("/api/v1/earnedcash/projects/p1/cases").get_json()["cases"] == []

    audit = http.get("/api/v1/earnedcash/audit").get_json()
    assert audit["valid"] is True
    assert audit["events"][-1]["event_type"] == "RECOVERY_QUEUE_REPLACED"


def test_persistent_route_rejects_self_attested_queue_creation(monkeypatch):
    store = EarnedCashStore.memory()
    http = client(monkeypatch, store)
    seed_pilot(http)
    response = http.post(
        "/api/v1/earnedcash/projects/p1/reconcile-ledger",
        json={"records": self_attested_chain()},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "verified_is_server_controlled"
    assert http.get("/api/v1/earnedcash/projects/p1/cases").get_json()["cases"] == []


def test_client_unknown_reconcile_clears_old_operator_queue(monkeypatch):
    store = EarnedCashStore.memory()
    http = client(monkeypatch, store)
    seed_pilot(http)
    store.replace_recovery_queue(
        tenant_id="tenant-test", project_id="p1", items=(queue_item(),)
    )
    assert len(http.get("/api/v1/earnedcash/projects/p1/cases").get_json()["cases"]) == 1

    response = http.post(
        "/api/v1/earnedcash/projects/p1/reconcile-ledger",
        json={"records": client_chain()},
    )
    assert response.status_code == 200
    assert response.get_json()["recovery_queue"] == []
    assert http.get("/api/v1/earnedcash/projects/p1/cases").get_json()["cases"] == []


def test_route_project_mismatch_is_rejected(monkeypatch):
    store = EarnedCashStore.memory()
    http = client(monkeypatch, store)
    seed_pilot(http)
    rows = client_chain(); rows[2]["project_id"] = "other"
    response = http.post(
        "/api/v1/earnedcash/projects/p1/reconcile-ledger", json={"records": rows}
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "route_project_mismatch"


def test_persistent_case_reads_are_tenant_scoped(monkeypatch):
    store = EarnedCashStore.memory()
    http = client(monkeypatch, store)
    seed_pilot(http)
    store.replace_recovery_queue(
        tenant_id="tenant-test", project_id="p1", items=(queue_item(),)
    )

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "other-tenant")
    response = http.get("/api/v1/earnedcash/projects/p1/cases")
    assert response.status_code == 200
    assert response.get_json()["cases"] == []
    assert http.get("/api/v1/earnedcash/audit").get_json()["events"] == []
