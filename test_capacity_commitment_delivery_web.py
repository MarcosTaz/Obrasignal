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
        "deadline": "2026-12-31",
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
    report = response.get_json()["delivery_report_markdown"]
    assert "Capacity Commitment Recovery Audit" in report
    assert "Recoverability state: **RECOVERABLE**" in report
    assert "Verified recovery: **NO**" in report
    assert "Payment received: **NO**" in report


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
    assert "not proof of payment" in text

    other = client.get(
        "/api/capacity/cases/tenant-report/report",
        headers=_headers("tenant-b"),
    )
    assert other.status_code == 404
    assert other.get_json()["error"] == "case_not_found"

    unauthenticated = client.get("/api/capacity/cases/tenant-report/report")
    assert unauthenticated.status_code == 401
