from decimal import Decimal

from factories.capacity_commitment.engine import ENGINE_VERSION
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def payload(case_id="web-case", **case_overrides):
    recovery_case = case(case_id, **case_overrides)
    return {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "program-ev-1",
        "contract_id": "lta-2026-01",
        "forecast_units": "120000",
        "recovery_case": recovery_case_to_payload(recovery_case),
        "evidence_refs": ["contract:12", "actuals:2026Q2"],
        "missing_evidence": [],
        "deadline": "2099-09-30",
    }


def headers(tenant="tenant-a", *, include_intent=True):
    values = {"X-Test-Tenant": tenant}
    if include_intent:
        values["X-Capacity-Intent"] = "create-case"
    return values


def app_for(tmp_path):
    repository = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repository, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return app, repository


def test_web_requires_authenticated_tenant(tmp_path):
    app, _ = app_for(tmp_path)
    response = app.test_client().get("/api/capacity/cases")
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"


def test_operator_console_is_authenticated_and_truth_labeled(tmp_path):
    app, _ = app_for(tmp_path)
    unauthenticated = app.test_client().get("/")
    assert unauthenticated.status_code == 401

    response = app.test_client().get("/", headers=headers(include_intent=False))
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Capacity Commitment" in text
    assert "Economic exposure is kept separate" in text
    assert "No result on this screen is a verified recovery or payment" in text
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_web_create_requires_explicit_same_origin_intent_header(tmp_path):
    app, _ = app_for(tmp_path)
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(include_intent=False),
        json=payload("missing-intent"),
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "create_intent_required"


def test_web_create_returns_truth_preserving_result_and_package(tmp_path):
    app, _ = app_for(tmp_path)
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=payload(),
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["case"]["forecast_units"] == "120000"
    assert body["case"]["committed_units"] == "100000"
    assert body["result"]["recoverability_state"] == "RECOVERABLE"
    assert body["result"]["recoverable_amount"] == "100000"
    assert body["result"]["engine_version"] == ENGINE_VERSION
    assert body["recovery_package"]["audit_trail"]["engine_version"] == ENGINE_VERSION
    assert body["recovery_package"]["assessment_date"]
    assert body["recovery_package"]["audit_trail"]["deadline_expired_by_date"] is False
    assert body["recovery_package"]["executive_summary"]["verified_recovery"] is False
    assert body["recovery_package"]["executive_summary"]["payment_received"] is False
    assert response.headers["Cache-Control"] == "no-store"


def test_web_forecast_only_keeps_exposure_but_zero_claimable(tmp_path):
    app, _ = app_for(tmp_path)
    request_payload = payload("forecast-only")
    request_payload["recovery_case"]["commitment_state"] = "FORECAST_ONLY"
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=request_payload,
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["result"]["economic_exposure"] == "100000"
    assert body["result"]["recoverability_state"] == "NON_RECOVERABLE"
    assert body["result"]["claimable_amount"] == "0"


def test_web_tenant_isolation_on_get_and_list(tmp_path):
    app, _ = app_for(tmp_path)
    client = app.test_client()
    created = client.post(
        "/api/capacity/cases",
        headers=headers("tenant-a"),
        json=payload("isolated-case"),
    )
    assert created.status_code == 201

    own = client.get(
        "/api/capacity/cases/isolated-case",
        headers=headers("tenant-a", include_intent=False),
    )
    assert own.status_code == 200

    other = client.get(
        "/api/capacity/cases/isolated-case",
        headers=headers("tenant-b", include_intent=False),
    )
    assert other.status_code == 404

    other_list = client.get(
        "/api/capacity/cases",
        headers=headers("tenant-b", include_intent=False),
    )
    assert other_list.status_code == 200
    assert other_list.get_json() == {"count": 0, "items": []}


def test_web_save_return_survives_repository_reopen(tmp_path):
    db_path = tmp_path / "capacity.db"
    first_repo = CapacityRepository(str(db_path))
    first_app = create_app(first_repo, lambda req: req.headers.get("X-Test-Tenant"))
    first_app.config.update(TESTING=True)
    created = first_app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=payload("restart-case"),
    )
    assert created.status_code == 201

    reopened_repo = CapacityRepository(str(db_path))
    reopened_app = create_app(reopened_repo, lambda req: req.headers.get("X-Test-Tenant"))
    reopened_app.config.update(TESTING=True)
    restored = reopened_app.test_client().get(
        "/api/capacity/cases/restart-case",
        headers=headers(include_intent=False),
    )
    assert restored.status_code == 200
    assert restored.get_json()["case"]["case_id"] == "restart-case"


def test_web_duplicate_creation_conflicts_and_preserves_first_snapshot(tmp_path):
    app, repository = app_for(tmp_path)
    client = app.test_client()
    first = payload("duplicate-case")
    created = client.post(
        "/api/capacity/cases",
        headers=headers(),
        json=first,
    )
    assert created.status_code == 201

    changed = payload("duplicate-case", actual_units=Decimal("0"))
    conflict = client.post(
        "/api/capacity/cases",
        headers=headers(),
        json=changed,
    )
    assert conflict.status_code == 409
    assert conflict.get_json()["error"] == "case_already_exists"

    restored = repository.load(tenant_id="tenant-a", case_id="duplicate-case")
    assert restored.recovery_case.actual_units == Decimal("80000")


def test_web_rejects_supported_evidence_without_persisted_refs(tmp_path):
    app, _ = app_for(tmp_path)
    request_payload = payload("evidence-gap")
    request_payload["evidence_refs"] = []
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=request_payload,
    )
    assert response.status_code == 400
    assert "evidence_supported requires" in response.get_json()["detail"]


def test_web_rejects_string_boolean_without_persisting(tmp_path):
    app, repository = app_for(tmp_path)
    request_payload = payload("string-boolean")
    request_payload["recovery_case"]["evidence_supported"] = "false"
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=request_payload,
    )
    assert response.status_code == 400
    assert "evidence_supported must be boolean" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


def test_web_rejects_invalid_numeric_without_persisting(tmp_path):
    app, repository = app_for(tmp_path)
    request_payload = payload("bad-number")
    request_payload["recovery_case"]["dedicated_cost"] = "not-a-number"
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=request_payload,
    )
    assert response.status_code == 400
    assert "dedicated_cost must be numeric" in response.get_json()["detail"]
    assert repository.list_case_ids(tenant_id="tenant-a") == []


def test_web_rejects_unknown_top_level_and_case_fields(tmp_path):
    app, _ = app_for(tmp_path)
    client = app.test_client()

    top = payload("unknown-top")
    top["invented"] = "value"
    top_response = client.post(
        "/api/capacity/cases",
        headers=headers(),
        json=top,
    )
    assert top_response.status_code == 400

    nested = payload("unknown-nested")
    nested["recovery_case"]["invented"] = True
    nested_response = client.post(
        "/api/capacity/cases",
        headers=headers(),
        json=nested,
    )
    assert nested_response.status_code == 400


def test_web_requires_contract_or_nomination_anchor(tmp_path):
    app, _ = app_for(tmp_path)
    request_payload = payload("no-anchor")
    request_payload.pop("contract_id")
    response = app.test_client().post(
        "/api/capacity/cases",
        headers=headers(),
        json=request_payload,
    )
    assert response.status_code == 400
    assert "contract_id or nomination_id" in response.get_json()["detail"]
