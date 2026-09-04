from decimal import Decimal

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


HEADERS = {"X-Test-Tenant": "tenant-a", "X-Capacity-Intent": "create-case"}


def request_payload(case_id: str, **case_overrides) -> dict:
    recovery_case = case(case_id, **case_overrides)
    return {
        "company_id": "supplier-pilot",
        "customer_id": "oem-pilot",
        "program_id": "program-pilot",
        "contract_id": "lta-pilot-2026",
        "nomination_id": None,
        "forecast_units": "120000",
        "recovery_case": recovery_case_to_payload(recovery_case),
        "evidence_refs": ["contract:lta-pilot-2026#volume", "actuals:pilot-period"],
        "missing_evidence": [],
        "deadline": "2099-09-30",
    }


@pytest.mark.parametrize(
    "case_id,overrides,expected_state,expected_claimable",
    [
        ("pilot-positive", {}, "RECOVERABLE", "100000"),
        ("pilot-forecast-only", {"commitment_state": "FORECAST_ONLY"}, "NON_RECOVERABLE", "0"),
        ("pilot-wrong-customer", {"customer_matches": False}, "UNKNOWN", "0"),
        ("pilot-wrong-contract", {"contract_matches": False}, "UNKNOWN", "0"),
        ("pilot-wrong-amendment", {"amendment_matches": False}, "UNKNOWN", "0"),
        ("pilot-wrong-amortization", {"amortization_verified": False}, "UNKNOWN", "0"),
        ("pilot-unverified-dedication", {"asset_dedication_verified": False}, "UNKNOWN", "0"),
        ("pilot-mitigation-unreviewed", {"mitigation_reviewed": False}, "UNKNOWN", "0"),
        ("pilot-prior-recovery-unreviewed", {"prior_recovery_reviewed": False}, "UNKNOWN", "0"),
        ("pilot-unverified-notice-window", {"notice_window_verified": False}, "UNKNOWN", "0"),
        ("pilot-expired", {"notice_valid": False}, "EXPIRED", "0"),
        ("pilot-zero-exposure", {"actual_units": Decimal("100000")}, "ZERO_EXPOSURE", "0"),
        ("pilot-mitigated", {"mitigation": Decimal("30000")}, "RECOVERABLE", "70000"),
    ],
)
def test_assisted_api_end_to_end_matrix(tmp_path, case_id, overrides, expected_state, expected_claimable):
    values = dict(overrides)
    commitment_override = values.pop("commitment_state", None)
    payload = request_payload(case_id, **values)
    if commitment_override is not None:
        payload["recovery_case"]["commitment_state"] = commitment_override

    db_path = tmp_path / "capacity.db"
    repository = CapacityRepository(str(db_path))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)

    response = app.test_client().post("/api/capacity/cases", headers=HEADERS, json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["result"]["recoverability_state"] == expected_state
    assert body["result"]["claimable_amount"] == expected_claimable
    assert body["recovery_package"]["executive_summary"]["verified_recovery"] is False
    assert body["recovery_package"]["executive_summary"]["payment_received"] is False
    assert body["recovery_package"]["audit_trail"]["deadline"] == "2099-09-30"
    assert body["recovery_package"]["assessment_date"]

    reopened = CapacityRepository(str(db_path))
    reopened_app = create_app(reopened, lambda req: req.headers.get("X-Test-Tenant"))
    reopened_app.config.update(TESTING=True)
    restored = reopened_app.test_client().get(
        f"/api/capacity/cases/{case_id}",
        headers={"X-Test-Tenant": "tenant-a"},
    )
    assert restored.status_code == 200
    assert restored.get_json()["result"]["claimable_amount"] == expected_claimable

    cross_tenant = reopened_app.test_client().get(
        f"/api/capacity/cases/{case_id}",
        headers={"X-Test-Tenant": "tenant-b"},
    )
    assert cross_tenant.status_code == 404


def test_timeout_style_exact_retry_is_idempotent_through_http(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    client = app.test_client()
    payload = request_payload("timeout-retry")

    first = client.post("/api/capacity/cases", headers=HEADERS, json=payload)
    retry = client.post("/api/capacity/cases", headers=HEADERS, json=payload)
    assert first.status_code == retry.status_code == 201
    assert first.get_json()["result"] == retry.get_json()["result"]
    assert repository.list_case_ids(tenant_id="tenant-a") == ["timeout-retry"]


def test_forecast_revision_cannot_change_firm_commitment_entitlement(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    client = app.test_client()

    low = request_payload("forecast-low")
    low["forecast_units"] = "1000"
    high = request_payload("forecast-high")
    high["forecast_units"] = "999999"

    low_response = client.post("/api/capacity/cases", headers=HEADERS, json=low)
    high_response = client.post("/api/capacity/cases", headers=HEADERS, json=high)
    assert low_response.status_code == high_response.status_code == 201
    low_body = low_response.get_json()
    high_body = high_response.get_json()
    assert low_body["case"]["committed_units"] == high_body["case"]["committed_units"] == "100000"
    assert low_body["result"]["claimable_amount"] == high_body["result"]["claimable_amount"] == "100000"
    assert low_body["case"]["forecast_units"] == "1000"
    assert high_body["case"]["forecast_units"] == "999999"


def test_forecast_only_remains_zero_claimable_even_with_extreme_forecast(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    payload = request_payload("forecast-context-only")
    payload["forecast_units"] = "999999999"
    payload["recovery_case"]["commitment_state"] = "FORECAST_ONLY"

    response = app.test_client().post("/api/capacity/cases", headers=HEADERS, json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["result"]["economic_exposure"] == "100000"
    assert body["result"]["claimable_amount"] == "0"
    assert body["result"]["recoverability_state"] == "NON_RECOVERABLE"


def test_verified_notice_window_without_deadline_fails_before_persistence(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    payload = request_payload("pilot-missing-deadline")
    payload["deadline"] = None

    response = app.test_client().post("/api/capacity/cases", headers=HEADERS, json=payload)
    assert response.status_code == 400
    assert "notice_window_verified requires" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


def test_operator_console_exposes_all_material_review_gates(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)

    response = app.test_client().get("/", headers={"X-Test-Tenant": "tenant-a"})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for label in (
        "Customer matches evidence?",
        "Contract matches evidence?",
        "Applicable amendment matches?",
        "Asset dedication verified?",
        "Mitigation reviewed?",
        "Prior recovery/payment reviewed?",
        "Notice window verified?",
        "Absolute notice deadline",
    ):
        assert label in html
