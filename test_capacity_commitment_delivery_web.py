from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def _payload(case_id="delivery-web"):
    return {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "program-1",
        "contract_id": "lta-2026-01",
        "nomination_id": "award-42",
        "forecast_units": "120000",
        "recovery_case": recovery_case_to_payload(case(case_id)),
        "evidence_refs": ["contract:lta-2026-01#12", "actuals:2026Q2"],
        "missing_evidence": [],
        "deadline": "2099-12-31",
    }


def _headers(tenant="tenant-a", *, create=False):
    values = {"X-Test-Tenant": tenant}
    if create:
        values["X-Capacity-Intent"] = "create-case"
    return values


def _app(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return app


def test_create_payload_includes_truth_preserving_markdown_report(tmp_path):
    app = _app(tmp_path)
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=_headers(create=True),
        json=_payload(),
    )

    assert response.status_code == 201
    body = response.get_json()
    report = body["delivery_report_markdown"]
    assert "Capacity Commitment Recovery Audit" in report
    assert "Recoverability state: **RECOVERABLE**" in report
    assert "Verified recovery: **NO**" in report
    assert "Payment received: **NO**" in report
    assert body["recovery_package"]["assessment_date"]
    assert body["recovery_package"]["audit_trail"]["deadline_expired_by_date"] is False


def test_report_endpoint_is_authenticated_tenant_scoped_and_no_store(tmp_path):
    app = _app(tmp_path)
    client = app.test_client()
    created = client.post(
        "/api/capacity/cases",
        headers=_headers(create=True),
        json=_payload("tenant-report"),
    )
    assert created.status_code == 201

    own = client.get(
        "/api/capacity/cases/tenant-report/report",
        headers=_headers("tenant-a"),
    )
    assert own.status_code == 200
    assert own.content_type.startswith("text/markdown")
    assert own.headers["Cache-Control"] == "no-store"
    text = own.get_data(as_text=True)
    assert "Supplier/company: `supplier-1`" in text
    assert "Assessment date:" in text
    assert "not proof of payment" in text

    other = client.get(
        "/api/capacity/cases/tenant-report/report",
        headers=_headers("tenant-b"),
    )
    assert other.status_code == 404
    assert other.get_json()["error"] == "case_not_found"

    unauthenticated = client.get("/api/capacity/cases/tenant-report/report")
    assert unauthenticated.status_code == 401


def test_report_is_deterministic_after_repository_restart_on_same_assessment_date(tmp_path):
    db_path = tmp_path / "capacity.db"
    first_repo = CapacityRepository(str(db_path))
    first_app = create_app(first_repo, lambda req: req.headers.get("X-Test-Tenant"))
    first_app.config.update(TESTING=True)
    first_client = first_app.test_client()

    created = first_client.post(
        "/api/capacity/cases",
        headers=_headers(create=True),
        json=_payload("stable-report"),
    )
    assert created.status_code == 201
    initial_report = created.get_json()["delivery_report_markdown"]

    reopened_repo = CapacityRepository(str(db_path))
    reopened_app = create_app(reopened_repo, lambda req: req.headers.get("X-Test-Tenant"))
    reopened_app.config.update(TESTING=True)
    reopened = reopened_app.test_client().get(
        "/api/capacity/cases/stable-report/report",
        headers=_headers(),
    )

    assert reopened.status_code == 200
    assert reopened.get_data(as_text=True) == initial_report
    assert "Verified recovery: **NO**" in initial_report
    assert "Payment received: **NO**" in initial_report
