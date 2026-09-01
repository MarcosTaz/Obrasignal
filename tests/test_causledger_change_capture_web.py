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
        "customer_ref": "oem-a",
        "program_ref": "program-a",
        "event_ref": "ECO-017",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-1",
        "cost_evidence_ref": "ledger-1",
        "currency": "EUR",
        "commercial_basis_content": "signed commercial basis",
        "event_evidence_content": "customer requested engineering change",
        "cost_evidence_content": "engineering cost ledger",
        "gross_cost": "12500",
        "notice_due": "2026-09-30",
    }


def test_case_creation_returns_active_change_sheet_prompt(tmp_path):
    database = tmp_path / "capture-web.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    created = analyst.post("/analyze", json=_payload())
    assert created.status_code == 201
    capture = created.get_json()["change_capture"]
    assert capture["window_state"] == "OPEN"
    assert capture["factual_window_hours"] == 72
    assert capture["fact_entry_allowed"] is True
    assert capture["download_prompt"]["active"] is True
    assert capture["download_prompt"]["stops_when_factual_window_closes"] is True
    assert capture["download_prompt"]["download_path"].endswith("/change-sheet")
    assert capture["download_prompt"]["message"].strip()


def test_client_can_add_simple_request_description_and_download_hashed_sheet(tmp_path):
    database = tmp_path / "capture-client.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    client = create_app(database, identity_resolver=_identity("tenant-a", "client-a", "client")).test_client()
    finding = analyst.post("/analyze", json=_payload()).get_json()["finding_id"]

    summary = client.post(
        f"/findings/{finding}/change-facts",
        json={
            "confirm_factual_entry": True,
            "fact_type": "REQUESTED_CHANGE",
            "fact_text": "Move the mounting holes 8 mm to clear the revised housing.",
            "source_ref": "customer-email-2026-08-31",
        },
    )
    assert summary.status_code == 201
    body = summary.get_json()
    assert body["fact_receipt"]["fact_hash"]
    assert body["capture"]["requested_change_source"] == "DECLARED_FACT"
    assert body["capture"]["download_prompt"]["active"] is True
    assert body["capture"]["download_prompt"]["message"].strip()
    assert body["capture"]["download_prompt"]["current_snapshot_exported"] is False

    declared_time = client.post(
        f"/findings/{finding}/change-facts",
        json={
            "confirm_factual_entry": True,
            "fact_type": "CHANGE_REQUESTED_AT",
            "fact_text": "2026-08-31T14:35:00+01:00",
            "source_ref": "customer-email-2026-08-31",
        },
    )
    assert declared_time.status_code == 201
    assert declared_time.get_json()["capture"]["declared_change_requested_at"] == "2026-08-31T13:35:00+00:00"
    assert declared_time.get_json()["capture"]["declared_change_requested_at_is_externally_verified"] is False

    downloaded = client.get(f"/findings/{finding}/change-sheet")
    assert downloaded.status_code == 200
    assert downloaded.headers["Content-Disposition"].startswith('attachment; filename="CausLedger-change-chg_')
    assert len(downloaded.headers["X-CausLedger-Sheet-SHA256"]) == 64
    assert downloaded.headers["X-CausLedger-Export-Receipt"].startswith("download_")
    assert downloaded.headers["X-CausLedger-Transfer-Completion-Proven"] == "false"
    assert downloaded.headers["X-CausLedger-Timestamp-State"] == "UNAVAILABLE"
    text = downloaded.get_data(as_text=True)
    assert "CAUSLEDGER — CHANGE CAPTURE SHEET" in text
    assert "Move the mounting holes 8 mm" in text
    assert "2026-08-31T13:35:00+00:00" in text
    assert "not a contractual notice deadline" in text
    assert downloaded.headers["Cache-Control"] == "no-store"

    status = client.get(f"/findings/{finding}/change-capture").get_json()
    assert status["download_count"] == 1
    assert status["download_prompt"]["active"] is False
    assert status["download_prompt"]["current_snapshot_exported"] is True
    assert status["download_reminder"]["state"] == "SATISFIED_CURRENT_SNAPSHOT"


def test_reviewer_alone_cannot_use_client_fact_capture_surface(tmp_path):
    database = tmp_path / "capture-role.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    reviewer = create_app(database, identity_resolver=_identity("tenant-a", "reviewer-a", "reviewer")).test_client()
    finding = analyst.post("/analyze", json=_payload()).get_json()["finding_id"]

    assert reviewer.get(f"/findings/{finding}/change-capture").status_code == 403
    assert reviewer.get(f"/findings/{finding}/change-sheet").status_code == 403
    assert reviewer.post(
        f"/findings/{finding}/change-facts",
        json={"confirm_factual_entry": True, "fact_type": "OTHER_FACT", "fact_text": "should not write"},
    ).status_code == 403


def test_other_tenant_cannot_learn_or_modify_change_capture(tmp_path):
    database = tmp_path / "capture-scope.sqlite3"
    analyst = create_app(database, identity_resolver=_identity("tenant-a", "analyst-a", "analyst")).test_client()
    other_client = create_app(database, identity_resolver=_identity("tenant-b", "client-b", "client")).test_client()
    finding = analyst.post("/analyze", json=_payload()).get_json()["finding_id"]

    status = other_client.get(f"/findings/{finding}/change-capture")
    write = other_client.post(
        f"/findings/{finding}/change-facts",
        json={"confirm_factual_entry": True, "fact_type": "OTHER_FACT", "fact_text": "cross tenant"},
    )
    assert status.status_code == 422
    assert write.status_code == 422
    assert "tenant-scoped industrial case not found" in status.get_json()["message"]
    assert "tenant-scoped industrial case not found" in write.get_json()["message"]
