import json
from pathlib import Path

from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app

CASES = Path("factory_cloud/public_shadow_cases.json")


def _headers(tenant):
    return {"X-Tenant-ID": tenant, "X-Actor-ID": "public-shadow-validator"}


def _case(case_id):
    data = json.loads(CASES.read_text(encoding="utf-8"))
    return next(item for item in data["cases"] if item["id"] == case_id)


def test_contractcredit_public_shadow_preserves_unknown_when_public_incident_cannot_establish_account_sla(tmp_path):
    case = _case("contractcredit-aws-lambda-2023")
    assert len(case["sources"]) == 2
    assert case["unknown"]
    client = create_contractcredit_app(tmp_path / "contractcredit.sqlite3").test_client()
    evidence = {
        "source_ref": case["id"],
        "sha256": case["evidence_sha256"],
        "provenance": "public_reconstruction",
        "authorized": True,
    }
    result = client.post("/shadow/analyze", headers=_headers("public-shadow-contractcredit"), json={
        "service_contract": evidence,
        "incident_evidence": evidence,
        "monthly_fee": "0",
        "credit_rate": "0",
        "notice_due": "2023-06-30",
    })
    assert result.status_code == 201
    body = result.get_json()
    assert body["pilot_state"] == "EVIDENCE_OR_ECONOMICS_UNRESOLVED"
    for key, value in case["expected"].items():
        assert body[key] == value
    assert body["potential_value"] == "0.00"


def test_aviation_public_shadow_preserves_unknown_without_specific_lease_and_event_evidence(tmp_path):
    case = _case("aviation-maintenance-reserve-public")
    assert len(case["sources"]) == 2
    assert case["unknown"]
    client = create_aviation_app(tmp_path / "aviation.sqlite3").test_client()
    evidence = {
        "source_ref": case["id"],
        "sha256": case["evidence_sha256"],
        "provenance": "public_reconstruction",
        "authorized": True,
    }
    result = client.post("/shadow/analyze", headers=_headers("public-shadow-aviation"), json={
        "lease_contract": evidence,
        "maintenance_event": evidence,
        "eligible_cost": "0",
        "reimbursed_amount": "0",
        "notice_due": "2026-12-31",
    })
    assert result.status_code == 201
    body = result.get_json()
    assert body["pilot_state"] == "EVIDENCE_OR_ECONOMICS_UNRESOLVED"
    for key, value in case["expected"].items():
        assert body[key] == value
    assert body["potential_value"] == "0"
