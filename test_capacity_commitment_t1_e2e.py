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
        "deadline": "2026-09-30",
    }


@pytest.mark.parametrize(
    "case_id,overrides,expected_state,expected_claimable",
    [
        ("pilot-positive", {}, "RECOVERABLE", "100000"),
        ("pilot-forecast-only", {"commitment_state": "FORECAST_ONLY"}, "NON_RECOVERABLE", "0"),
        ("pilot-wrong-amortization", {"amortization_verified": False}, "UNKNOWN", "0"),
        ("pilot-unverified-notice-window", {"notice_window_verified": False}, "UNKNOWN", "0"),
        ("pilot-expired", {"notice_valid": False}, "EXPIRED", "0"),
        ("pilot-zero-exposure", {"actual_units": Decimal("100000")}, "ZERO_EXPOSURE", "0"),
        ("pilot-mitigated", {"mitigation": Decimal("30000")}, "RECOVERABLE", "70000"),
    ],
)
def test_assisted_api_end_to_end_matrix(tmp_path, case_id, overrides, expected_state, expected_claimable):
    # Serialized enum overrides are applied after constructing a valid typed case.
    commitment_override = overrides.pop("commitment_state", None)
    payload = request_payload(case_id, **overrides)
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
    assert body["recovery_package"]["audit_trail"]["deadline"] == "2026-09-30"

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


def test_operator_console_exposes_notice_window_verification(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)

    response = app.test_client().get("/", headers={"X-Test-Tenant": "tenant-a"})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Notice window verified?" in html
    assert "Absolute notice deadline" in html
