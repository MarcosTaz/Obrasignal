from factory_cloud.assurance_backup import create_backup, restore_backup
from factory_cloud.assurance_store import AssuranceStore
from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app


def _headers(tenant, actor="synthetic-analyst", *, support=False):
    headers = {"X-Tenant-ID": tenant, "X-Actor-ID": actor}
    if support:
        headers["X-Support-Role"] = "on_call"
    return headers


def _evidence(ref, digit):
    return {"source_ref": ref, "sha256": digit * 64, "provenance": "synthetic_company_fixture", "authorized": True}


def _exercise_support(client, tenant):
    headers = _headers(tenant, "synthetic-support", support=True)
    opened = client.post("/support/incidents", headers=headers, json={
        "incident_id": "synthetic-support-1", "severity": "P1", "summary": "synthetic continuity incident",
    })
    assert opened.status_code == 201
    for target in ("ACKNOWLEDGED", "INVESTIGATING", "MITIGATED"):
        transitioned = client.post(
            "/support/incidents/synthetic-support-1/transition", headers=headers, json={"target": target}
        )
        assert transitioned.status_code == 200
        assert transitioned.get_json()["state"] == target
    updated = client.post(
        "/support/incidents/synthetic-support-1/customer-update", headers=headers,
        json={"communication_evidence_ref": "synthetic-update"},
    )
    assert updated.status_code == 200
    resolved = client.post(
        "/support/incidents/synthetic-support-1/transition", headers=headers,
        json={"target": "RESOLVED", "evidence_ref": "synthetic-closure"},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["state"] == "RESOLVED"


def _backup_and_prove(database, tmp_path, tenant):
    backup = tmp_path / f"{tenant}.backup.sqlite3"
    restored = tmp_path / f"{tenant}.restored.sqlite3"
    receipt = create_backup(database, backup)
    restore_backup(backup, restored, expected_sha256=receipt.sha256)
    store = AssuranceStore(restored)
    assert store.count("findings", tenant) == 1
    assert store.count("audit_events", tenant) >= 1


def test_contractcredit_synthetic_company_a_runs_product_and_operations_end_to_end(tmp_path):
    tenant = "synthetic-company-contractcredit-a"
    database = tmp_path / "contractcredit.sqlite3"
    client = create_contractcredit_app(database).test_client()
    assert client.get("/").status_code == 200
    assert client.get("/ready").get_json()["status"] == "ready"

    analyzed = client.post("/shadow/analyze", headers=_headers(tenant), json={
        "service_contract": _evidence("msa-v1.pdf", "a"),
        "incident_evidence": _evidence("incident-v1.pdf", "b"),
        "monthly_fee": "50000", "credit_rate": "0.10", "notice_due": "2026-09-15",
    })
    assert analyzed.status_code == 201
    finding_id = analyzed.get_json()["finding_id"]
    assert analyzed.get_json()["entitlement_state"] == "UNKNOWN"

    hostile = client.post(
        f"/findings/{finding_id}/review", headers=_headers("hostile-tenant", "hostile"),
        json={"approved": True, "reason": "must fail"},
    )
    assert hostile.status_code == 422

    reviewed = client.post(
        f"/findings/{finding_id}/review", headers=_headers(tenant, "synthetic-reviewer"),
        json={"approved": True, "reason": "synthetic evidence reviewed"},
    )
    assert reviewed.get_json()["state"] == "APPROVED"
    assert client.post(f"/findings/{finding_id}/action", headers=_headers(tenant)).get_json()["state"] == "ACTIONED"
    resolved = client.post(f"/findings/{finding_id}/resolve", headers=_headers(tenant), json={
        "outcome_id": "synthetic-outcome-1", "recovered_amount": "5000",
        "currency": "EUR", "evidence_ref": "synthetic-credit-note",
    })
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"
    assert client.get("/ready").get_json()["open_findings"] == 0

    _backup_and_prove(database, tmp_path, tenant)
    _exercise_support(client, tenant)


def test_aviation_synthetic_company_b_runs_product_and_operations_end_to_end(tmp_path):
    tenant = "synthetic-company-aviation-b"
    database = tmp_path / "aviation.sqlite3"
    client = create_aviation_app(database).test_client()
    assert client.get("/").status_code == 200
    assert client.get("/ready").get_json()["status"] == "ready"

    analyzed = client.post("/shadow/analyze", headers=_headers(tenant), json={
        "lease_contract": _evidence("lease-v1.pdf", "c"),
        "maintenance_event": _evidence("shop-v1.pdf", "d"),
        "eligible_cost": "100000", "reimbursed_amount": "25000", "notice_due": "2026-09-30",
    })
    assert analyzed.status_code == 201
    finding_id = analyzed.get_json()["finding_id"]
    assert analyzed.get_json()["entitlement_state"] == "UNKNOWN"
    assert client.post(
        f"/findings/{finding_id}/review", headers=_headers(tenant, "synthetic-reviewer"),
        json={"approved": True, "reason": "synthetic evidence reviewed"},
    ).get_json()["state"] == "APPROVED"
    assert client.post(f"/findings/{finding_id}/action", headers=_headers(tenant)).get_json()["state"] == "ACTIONED"
    resolved = client.post(f"/findings/{finding_id}/resolve", headers=_headers(tenant), json={
        "outcome_id": "synthetic-outcome-2", "recovered_amount": "75000",
        "currency": "EUR", "evidence_ref": "synthetic-settlement",
    })
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"

    _backup_and_prove(database, tmp_path, tenant)
    _exercise_support(client, tenant)
