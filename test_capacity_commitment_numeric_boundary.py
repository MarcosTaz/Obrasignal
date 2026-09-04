from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def _app(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return app, repository


def _payload(case_id: str):
    return {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "program-1",
        "contract_id": "lta-1",
        "forecast_units": "120000",
        "recovery_case": recovery_case_to_payload(case(case_id)),
        "evidence_refs": ["contract:1"],
        "missing_evidence": [],
        "deadline": "2099-12-31",
    }


def _post(client, payload):
    return client.post(
        "/api/capacity/cases",
        headers={"X-Test-Tenant": "tenant-a", "X-Capacity-Intent": "create-case"},
        json=payload,
    )


def test_web_rejects_binary_float_for_financial_case_value(tmp_path):
    app, repository = _app(tmp_path)
    payload = _payload("float-cost")
    payload["recovery_case"]["dedicated_cost"] = 10000000000000000000.125

    response = _post(app.test_client(), payload)

    assert response.status_code == 400
    assert "dedicated_cost must be an exact decimal string or integer" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


def test_web_rejects_binary_float_for_forecast_context(tmp_path):
    app, repository = _app(tmp_path)
    payload = _payload("float-forecast")
    payload["forecast_units"] = 10000000000000000000.125

    response = _post(app.test_client(), payload)

    assert response.status_code == 400
    assert "forecast_units must be an exact decimal string or integer" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


def test_web_accepts_exact_decimal_strings_and_integer_values(tmp_path):
    app, _repository = _app(tmp_path)
    payload = _payload("exact-values")
    payload["recovery_case"]["dedicated_cost"] = "10000000000000000000.125"
    payload["forecast_units"] = 120000

    response = _post(app.test_client(), payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["case"]["forecast_units"] == "120000"
    assert body["recovery_package"]["investment_exposure"]["dedicated_cost"] == "10000000000000000000.125"
