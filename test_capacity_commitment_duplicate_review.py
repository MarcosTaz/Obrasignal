from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def test_positive_case_cannot_assume_no_duplicate_without_review(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)

    recovery = recovery_case_to_payload(case("duplicate-review-missing"))
    recovery.pop("duplicate_claim_reviewed", None)
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

    assert response.status_code == 201
    body = response.get_json()
    assert body["result"]["recoverability_state"] == "UNKNOWN"
    assert body["result"]["claimable_amount"] == "0"
    assert body["result"]["reasons"] == ["duplicate_claim_review_unknown"]
