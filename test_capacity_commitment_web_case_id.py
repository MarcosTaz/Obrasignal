import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def _app(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return app, repository


def _payload(case_id):
    return {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "programme-1",
        "contract_id": "lta-1",
        "recovery_case": recovery_case_to_payload(case(case_id)),
        "evidence_refs": ["contract:1"],
        "missing_evidence": [],
        "deadline": "2099-12-31",
    }


@pytest.mark.parametrize(
    "case_id",
    [
        "case/with/slash",
        "case\\with\\backslash",
        "case?query",
        "case#fragment",
        "case with space",
        "`case`",
    ],
)
def test_web_rejects_case_ids_that_cannot_be_safely_addressed(case_id, tmp_path):
    app, repository = _app(tmp_path)
    response = app.test_client().post(
        "/api/capacity/cases",
        headers={"X-Test-Tenant": "tenant-a", "X-Capacity-Intent": "create-case"},
        json=_payload(case_id),
    )

    assert response.status_code == 400
    assert "case_id must be URL-addressable" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


@pytest.mark.parametrize("case_id", [None, 0, True, [], {}])
def test_web_rejects_non_string_case_ids_as_400_without_persisting(case_id, tmp_path):
    app, repository = _app(tmp_path)
    response = app.test_client().post(
        "/api/capacity/cases",
        headers={"X-Test-Tenant": "tenant-a", "X-Capacity-Intent": "create-case"},
        json=_payload(case_id),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"
    assert "case_id must be URL-addressable" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


def test_web_accepts_and_retrieves_safe_case_id(tmp_path):
    app, _ = _app(tmp_path)
    client = app.test_client()
    case_id = "OEM42:PROGRAM_7.case-1"

    created = client.post(
        "/api/capacity/cases",
        headers={"X-Test-Tenant": "tenant-a", "X-Capacity-Intent": "create-case"},
        json=_payload(case_id),
    )
    assert created.status_code == 201

    restored = client.get(
        f"/api/capacity/cases/{case_id}",
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert restored.status_code == 200
    assert restored.get_json()["case"]["case_id"] == case_id

    report = client.get(
        f"/api/capacity/cases/{case_id}/report",
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert report.status_code == 200
    assert case_id in report.get_data(as_text=True)
