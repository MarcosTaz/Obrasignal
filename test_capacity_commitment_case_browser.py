from factories.capacity_commitment.case_browser import render_case_browser
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def _payload(case_id):
    return {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "programme-1",
        "contract_id": "lta-1",
        "recovery_case": recovery_case_to_payload(case(case_id)),
        "evidence_refs": ["contract:1"],
        "missing_evidence": [],
        "deadline": "2026-12-31",
    }


def _app(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return app


def _create(client, tenant, case_id):
    response = client.post(
        "/api/capacity/cases",
        headers={"X-Test-Tenant": tenant, "X-Capacity-Intent": "create-case"},
        json=_payload(case_id),
    )
    assert response.status_code == 201


def test_root_links_to_existing_case_browser(tmp_path):
    app = _app(tmp_path)
    response = app.test_client().get("/", headers={"X-Test-Tenant": "tenant-a"})
    assert response.status_code == 200
    assert 'href="/cases"' in response.get_data(as_text=True)
    assert "Open existing tenant cases" in response.get_data(as_text=True)


def test_case_browser_requires_auth_and_lists_only_current_tenant(tmp_path):
    app = _app(tmp_path)
    client = app.test_client()
    _create(client, "tenant-a", "tenant-a-case")
    _create(client, "tenant-b", "tenant-b-case")

    unauth = client.get("/cases")
    assert unauth.status_code == 401

    response = client.get("/cases", headers={"X-Test-Tenant": "tenant-a"})
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "tenant-a-case" in text
    assert "tenant-b-case" not in text
    assert "/api/capacity/cases/tenant-a-case/report" in text
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_case_browser_empty_state_is_explicit(tmp_path):
    app = _app(tmp_path)
    response = app.test_client().get("/cases", headers={"X-Test-Tenant": "tenant-a"})
    assert response.status_code == 200
    assert "No cases recorded for this tenant." in response.get_data(as_text=True)


def test_case_browser_renderer_escapes_untrusted_labels_even_if_called_directly():
    hostile = '<script>alert("x")</script>'
    html = render_case_browser([hostile])
    assert hostile not in html
    assert "&lt;script&gt;" in html
    assert "%3Cscript%3Ealert%28%22x%22%29%3C%2Fscript%3E" in html
