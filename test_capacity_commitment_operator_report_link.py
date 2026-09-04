from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.web import create_app


def test_operator_console_exposes_report_link_only_as_post_success_wiring(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)

    response = app.test_client().get("/", headers={"X-Test-Tenant": "tenant-a"})
    assert response.status_code == 200
    text = response.get_data(as_text=True)

    assert 'id="report-link"' in text
    assert "Open buyer-ready Markdown report" in text
    assert "encodeURIComponent(body.case.case_id)" in text
    assert "reportLink.style.display='none'" in text
    assert "reportLink.style.display='inline-block'" in text
    assert 'pattern="[A-Za-z0-9][A-Za-z0-9._:-]{0,199}"' in text
    assert 'name="duplicate_claim_reviewed"' in text
    assert "duplicate_claim_reviewed:tri(d.get('duplicate_claim_reviewed'))" in text
    assert 'name="duplicate_claim_reviewed"><option value="unknown">Unknown</option>' in text