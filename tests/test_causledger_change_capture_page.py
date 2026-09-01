from __future__ import annotations

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app as _create_app


def create_app(*args, **kwargs):
    kwargs.setdefault("allow_inline_evidence_content", True)
    return _create_app(*args, **kwargs)


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _payload():
    return {
        "customer_ref": "PRIVATE-CUSTOMER-NAME",
        "program_ref": "PRIVATE-PROGRAM-NAME",
        "event_ref": "ECO-017",
        "claim_family": "NRE",
        "commercial_basis_ref": "PRIVATE-PO-1",
        "cost_evidence_ref": "PRIVATE-LEDGER-1",
        "currency": "EUR",
        "commercial_basis_content": "private commercial basis",
        "event_evidence_content": "customer requested engineering change",
        "cost_evidence_content": "private cost ledger",
        "gross_cost": "999999",
        "notice_due": "2026-09-30",
    }


def test_client_page_contains_active_download_reminder_without_economic_or_customer_data(tmp_path):
    database = tmp_path / "client-page.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    client = create_app(database, identity_resolver=_identity("tenant-a", "client-a", "client")).test_client()
    finding = analyst.post("/analyze", json=_payload()).get_json()["finding_id"]

    response = client.get(f"/findings/{finding}/change-capture/view")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "CausLedger" in html
    assert "Do this before the factual window closes" in html
    assert "What was requested? One sentence." in html
    assert "Download change sheet" in html
    assert "ECO-017" in html
    for private_value in (
        "PRIVATE-CUSTOMER-NAME",
        "PRIVATE-PROGRAM-NAME",
        "PRIVATE-PO-1",
        "PRIVATE-LEDGER-1",
        "999999",
    ):
        assert private_value not in html
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]


def test_reviewer_cannot_open_client_change_page(tmp_path):
    database = tmp_path / "client-page-role.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("tenant-a", "reviewer-a", "reviewer")).test_client()
    finding = analyst.post("/analyze", json=_payload()).get_json()["finding_id"]

    response = reviewer.get(f"/findings/{finding}/change-capture/view")
    assert response.status_code == 403
    assert response.get_json() == {"error": "authorization_denied"}
