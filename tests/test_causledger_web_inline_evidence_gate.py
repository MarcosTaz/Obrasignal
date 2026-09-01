from auth_context import RequestIdentity
from vertical_apps.industrial_claims.web import create_app


def _identity(tenant_id: str, actor_id: str, *roles: str):
    return lambda: RequestIdentity(
        account_id=tenant_id,
        authenticated=True,
        subject=actor_id,
        claims={"sub": actor_id, "roles": list(roles)},
    )


def _candidate_payload():
    return {
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "change-1",
        "claim_family": "NRE",
        "commercial_basis_ref": "po-1",
        "cost_evidence_ref": "ledger-1",
        "currency": "EUR",
        "commercial_basis_content": "signed purchase order terms",
        "event_evidence_content": "customer directed engineering change",
        "cost_evidence_content": "engineering time ledger",
        "gross_cost": "10000",
        "avoided_cost": "0",
        "prior_payment": "0",
        "notice_due": "2026-09-30",
    }


def _synthetic_clients(database):
    analyst = create_app(
        database,
        identity_resolver=_identity("alpha", "analyst-1", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()
    reviewer = create_app(
        database,
        identity_resolver=_identity("alpha", "reviewer-1", "reviewer"),
        allow_inline_evidence_content=True,
    ).test_client()
    operator = create_app(
        database,
        identity_resolver=_identity("alpha", "operator-1", "operator"),
        allow_inline_evidence_content=True,
    ).test_client()
    return analyst, reviewer, operator


def test_default_runtime_rejects_inline_analysis_before_durable_mutation(tmp_path):
    database = tmp_path / "strict-analyze.sqlite3"
    analyst = create_app(
        database,
        identity_resolver=_identity("alpha", "analyst-1", "analyst"),
    ).test_client()
    reviewer = create_app(
        database,
        identity_resolver=_identity("alpha", "reviewer-1", "reviewer"),
    ).test_client()

    denied = analyst.post("/analyze", json=_candidate_payload())
    assert denied.status_code == 422
    assert denied.get_json()["message"] == (
        "inline documentary content is disabled; use authorized secure evidence capture"
    )

    queue = reviewer.get("/findings")
    assert queue.status_code == 200
    assert queue.get_json()["count"] == 0


def test_default_runtime_allows_reference_only_analysis_but_keeps_it_unresolved(tmp_path):
    database = tmp_path / "reference-only.sqlite3"
    analyst = create_app(
        database,
        identity_resolver=_identity("alpha", "analyst-1", "analyst"),
    ).test_client()
    payload = _candidate_payload()
    for field in (
        "commercial_basis_content",
        "event_evidence_content",
        "cost_evidence_content",
    ):
        payload.pop(field)

    response = analyst.post("/analyze", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["state"] == "UNRESOLVED_EVIDENCE"
    assert set(body["evidence_states"].values()) == {"REFERENCE_ONLY"}


def test_default_runtime_rejects_inline_amendment_without_creating_successor(tmp_path):
    database = tmp_path / "strict-amend.sqlite3"
    synthetic_analyst, _reviewer, _operator = _synthetic_clients(database)
    created = synthetic_analyst.post("/analyze", json=_candidate_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]

    strict_analyst = create_app(
        database,
        identity_resolver=_identity("alpha", "analyst-2", "analyst"),
    ).test_client()
    payload = _candidate_payload()
    payload["gross_cost"] = "12000"
    denied = strict_analyst.post(f"/findings/{finding_id}/amend", json=payload)
    assert denied.status_code == 422
    assert "inline documentary content is disabled" in denied.get_json()["message"]

    original = strict_analyst.get(f"/findings/{finding_id}")
    assert original.status_code == 200
    detail = original.get_json()
    assert detail["case"]["finding_id"] == finding_id
    assert detail["finding"]["state"] == "READY_FOR_REVIEW"
    assert detail["revision"]["is_current"] is True
    assert detail["revision"]["superseded_by_finding_id"] is None


def test_default_runtime_rejects_inline_outcome_evidence_before_closure(tmp_path):
    database = tmp_path / "strict-resolve.sqlite3"
    analyst, reviewer, operator = _synthetic_clients(database)
    created = analyst.post("/analyze", json=_candidate_payload())
    assert created.status_code == 201
    finding_id = created.get_json()["finding_id"]
    assert reviewer.post(
        f"/findings/{finding_id}/review",
        json={"approved": True, "reason": "synthetic internal review"},
    ).status_code == 200
    assert operator.post(f"/findings/{finding_id}/action").status_code == 200

    strict_operator = create_app(
        database,
        identity_resolver=_identity("alpha", "operator-2", "operator"),
    ).test_client()
    denied = strict_operator.post(
        f"/findings/{finding_id}/resolve",
        json={
            "outcome_id": "payment-1",
            "recovered_amount": "5000",
            "currency": "EUR",
            "evidence_ref": "bank-1",
            "evidence_content": "bank statement settlement evidence",
            "final_cumulative": True,
        },
    )
    assert denied.status_code == 422
    assert "inline documentary content is disabled" in denied.get_json()["message"]

    strict_operator_read = strict_operator.get(f"/findings/{finding_id}")
    assert strict_operator_read.status_code == 200
    assert strict_operator_read.get_json()["finding"]["state"] == "ACTIONED"
    assert strict_operator_read.get_json()["outcomes"] == []


def test_inline_mode_requires_explicit_opt_in_and_is_visible_in_health(tmp_path):
    database = tmp_path / "health.sqlite3"
    strict = create_app(
        database,
        identity_resolver=_identity("alpha", "analyst-1", "analyst"),
    ).test_client()
    synthetic = create_app(
        database,
        identity_resolver=_identity("alpha", "analyst-1", "analyst"),
        allow_inline_evidence_content=True,
    ).test_client()

    assert strict.get("/health").get_json()["inline_documentary_content_enabled"] is False
    assert synthetic.get("/health").get_json()["inline_documentary_content_enabled"] is True
    assert synthetic.post("/analyze", json=_candidate_payload()).status_code == 201


def test_default_console_hides_raw_document_and_outcome_forms_but_synthetic_mode_exposes_them(tmp_path):
    database = tmp_path / "console-gate.sqlite3"
    strict = create_app(database).test_client()
    synthetic = create_app(database, allow_inline_evidence_content=True).test_client()

    strict_html = strict.get("/").get_data(as_text=True)
    assert 'name="commercial_basis_content"' not in strict_html
    assert 'name="event_evidence_content"' not in strict_html
    assert 'name="cost_evidence_content"' not in strict_html
    assert 'id="resolve-form"' not in strict_html
    assert "Reference-only intake" in strict_html
    assert "authorized secure evidence-capture path" in strict_html
    assert "Do not paste bank statements" in strict_html

    synthetic_html = synthetic.get("/").get_data(as_text=True)
    assert 'name="commercial_basis_content"' in synthetic_html
    assert 'name="event_evidence_content"' in synthetic_html
    assert 'name="cost_evidence_content"' in synthetic_html
    assert 'id="resolve-form"' in synthetic_html
    assert "Synthetic/local mode is active" in synthetic_html
