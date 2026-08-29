from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def test_web_rejects_decimal_outside_engine_arithmetic_range_without_500(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)

    recovery = recovery_case_to_payload(case("decimal-out-of-range"))
    recovery["dedicated_cost"] = "1e1000000"
    payload = {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "program-1",
        "contract_id": "lta-1",
        "forecast_units": "120000",
        "recovery_case": recovery,
        "evidence_refs": ["contract:1"],
        "missing_evidence": [],
        "deadline": "2099-12-31",
    }

    response = app.test_client().post(
        "/api/capacity/cases",
        headers={"X-Test-Tenant": "tenant-a", "X-Capacity-Intent": "create-case"},
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"
    assert "engine arithmetic range" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []
