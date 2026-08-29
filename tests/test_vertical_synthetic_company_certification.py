from factory_cloud.assurance_backup import create_backup, restore_backup
from factory_cloud.assurance_observability import assurance_health
from factory_cloud.assurance_store import AssuranceStore
from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier, signed_test_headers
from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app

SECRET = "s" * 32
NOW = 1_800_000_000
VERIFIER = TrustedUpstreamVerifier(SECRET, clock=lambda: NOW)


def _headers(tenant, actor="synthetic-analyst", *, method="POST", path="/shadow/analyze", support=False):
    return signed_test_headers(
        secret=SECRET, tenant_id=tenant, actor_id=actor,
        method=method, path=path, timestamp=NOW,
        support_role=("on_call" if support else ""),
    )


def _evidence(ref, digit):
    return {"source_ref": ref, "sha256": digit * 64, "provenance": "synthetic_company_fixture", "authorized": True}


def _exercise_support(client, tenant):
    open_path = "/support/incidents"
    opened = client.post(open_path, headers=_headers(tenant, "synthetic-support", path=open_path, support=True), json={
        "incident_id": "synthetic-support-1", "severity": "P1", "summary": "synthetic continuity incident",
    })
    assert opened.status_code == 201
    transition_path = "/support/incidents/synthetic-support-1/transition"
    for target in ("ACKNOWLEDGED", "INVESTIGATING", "MITIGATED"):
        transitioned = client.post(
            transition_path,
            headers=_headers(tenant, "synthetic-support", path=transition_path, support=True),
            json={"target": target},
        )
        assert transitioned.status_code == 200
        assert transitioned.get_json()["state"] == target
    update_path = "/support/incidents/synthetic-support-1/customer-update"
    updated = client.post(
        update_path,
        headers=_headers(tenant, "synthetic-support", path=update_path, support=True),
        json={"communication_evidence_ref": "synthetic-update"},
    )
    assert updated.status_code == 200
    resolved = client.post(
        transition_path,
        headers=_headers(tenant, "synthetic-support", path=transition_path, support=True),
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


def _complete_finding(client, tenant, finding_id, *, recovered_amount, outcome_id, evidence_ref):
    review_path = f"/findings/{finding_id}/review"
    reviewed = client.post(
        review_path, headers=_headers(tenant, "synthetic-reviewer", path=review_path),
        json={"approved": True, "reason": "synthetic evidence reviewed"},
    )
    assert reviewed.get_json()["state"] == "APPROVED"
    action_path = f"/findings/{finding_id}/action"
    assert client.post(action_path, headers=_headers(tenant, path=action_path)).get_json()["state"] == "ACTIONED"
    resolve_path = f"/findings/{finding_id}/resolve"
    resolved = client.post(resolve_path, headers=_headers(tenant, path=resolve_path), json={
        "outcome_id": outcome_id, "recovered_amount": recovered_amount,
        "currency": "EUR", "evidence_ref": evidence_ref,
    })
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"


def test_contractcredit_synthetic_company_a_runs_product_and_operations_end_to_end(tmp_path):
    tenant = "synthetic-company-contractcredit-a"
    database = tmp_path / "contractcredit.sqlite3"
    client = create_contractcredit_app(database, identity_resolver=VERIFIER.verify_request).test_client()
    assert client.get("/").status_code == 200
    ready = client.get("/ready").get_json()
    assert ready["status"] == "ready"
    assert "open_findings" not in ready

    analyzed = client.post("/shadow/analyze", headers=_headers(tenant), json={
        "service_contract": _evidence("msa-v1.pdf", "a"),
        "incident_evidence": _evidence("incident-v1.pdf", "b"),
        "monthly_fee": "50000", "credit_rate": "0.10", "notice_due": "2026-09-15",
    })
    assert analyzed.status_code == 201
    finding_id = analyzed.get_json()["finding_id"]
    assert analyzed.get_json()["entitlement_state"] == "UNKNOWN"

    review_path = f"/findings/{finding_id}/review"
    hostile = client.post(
        review_path, headers=_headers("hostile-tenant", "hostile", path=review_path),
        json={"approved": True, "reason": "must fail"},
    )
    assert hostile.status_code == 422

    _complete_finding(
        client, tenant, finding_id, recovered_amount="5000",
        outcome_id="synthetic-outcome-1", evidence_ref="synthetic-credit-note",
    )
    assert assurance_health(database).operational_dict()["open_findings"] == 0
    _backup_and_prove(database, tmp_path, tenant)
    _exercise_support(client, tenant)


def test_aviation_synthetic_company_b_runs_product_and_operations_end_to_end(tmp_path):
    tenant = "synthetic-company-aviation-b"
    database = tmp_path / "aviation.sqlite3"
    client = create_aviation_app(database, identity_resolver=VERIFIER.verify_request).test_client()
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
    _complete_finding(
        client, tenant, finding_id, recovered_amount="75000",
        outcome_id="synthetic-outcome-2", evidence_ref="synthetic-settlement",
    )
    assert assurance_health(database).operational_dict()["open_findings"] == 0
    _backup_and_prove(database, tmp_path, tenant)
    _exercise_support(client, tenant)
