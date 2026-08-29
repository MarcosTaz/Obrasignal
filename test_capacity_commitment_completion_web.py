from decimal import Decimal

from factories.capacity_commitment.application import create_completion_app
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case


def headers(tenant="tenant-a", intent=None):
    result = {"X-Test-Tenant": tenant}
    if intent:
        result["X-Capacity-Intent"] = intent
    return result


def make_client(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_completion_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return repo, app.test_client()


def save_case(repo, *, tenant="tenant-a", case_id="case-1"):
    repo.save(
        AssistedCaseState(
            tenant_id=tenant,
            company_id="supplier-1",
            customer_id="oem-1",
            program_id="program-1",
            recovery_case=case(case_id, currency="EUR"),
            evidence_refs=("contract:1",),
            contract_id="lta-1",
            deadline="2099-09-30",
        )
    )


def engagement_payload():
    return {
        "engagement_id": "eng-1",
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "program-1",
        "currency": "EUR",
    }


def event_payload(event_id, event_type, **overrides):
    payload = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-08-29T20:00:00Z",
        "case_id": "case-1",
        "external_ref": "buyer-thread:1",
        "note": "synthetic workflow evidence",
    }
    payload.update(overrides)
    return payload


def test_completion_engagement_requires_intent_and_is_tenant_scoped(tmp_path):
    _repo, client = make_client(tmp_path)
    denied = client.post("/api/capacity/engagements", headers=headers(), json=engagement_payload())
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "engagement_intent_required"

    created = client.post(
        "/api/capacity/engagements",
        headers=headers(intent="create-engagement"),
        json=engagement_payload(),
    )
    assert created.status_code == 201
    assert created.get_json()["engagement"]["engagement_id"] == "eng-1"

    assert client.get("/api/capacity/engagements", headers=headers("tenant-a")).get_json()["count"] == 1
    assert client.get("/api/capacity/engagements", headers=headers("tenant-b")).get_json()["count"] == 0


def test_completion_action_outcome_and_payment_summary_preserves_truth_categories(tmp_path):
    repo, client = make_client(tmp_path)
    save_case(repo)
    client.post(
        "/api/capacity/engagements",
        headers=headers(intent="create-engagement"),
        json=engagement_payload(),
    )

    for payload in (
        event_payload("link", "CASE_LINKED"),
        event_payload("submit", "ACTION_SUBMITTED"),
        event_payload(
            "customer-cash",
            "CUSTOMER_RECOVERY_RECEIVED",
            amount="125000.50",
            currency="EUR",
        ),
        event_payload(
            "invoice",
            "OUR_INVOICE_ISSUED",
            case_id=None,
            amount="3500",
            currency="EUR",
        ),
        event_payload(
            "our-cash",
            "OUR_PAYMENT_RECEIVED",
            case_id=None,
            amount="3500",
            currency="EUR",
        ),
    ):
        response = client.post(
            "/api/capacity/engagements/eng-1/events",
            headers=headers(intent="record-event"),
            json=payload,
        )
        assert response.status_code == 201

    detail = client.get("/api/capacity/engagements/eng-1", headers=headers()).get_json()
    assert detail["summary"]["customer_recovery_received"] == "125000.50"
    assert detail["summary"]["our_invoice_issued"] == "3500"
    assert detail["summary"]["our_payment_received"] == "3500"
    assert detail["summary"]["action_submitted"] is True
    assert len(detail["events"]) == 5


def test_completion_zero_outcome_is_valid_and_not_recovery(tmp_path):
    repo, client = make_client(tmp_path)
    save_case(repo)
    client.post(
        "/api/capacity/engagements",
        headers=headers(intent="create-engagement"),
        json=engagement_payload(),
    )
    response = client.post(
        "/api/capacity/engagements/eng-1/events",
        headers=headers(intent="record-event"),
        json=event_payload("zero", "OUTCOME_ZERO_CONFIRMED"),
    )
    assert response.status_code == 201
    summary = response.get_json()["summary"]
    assert summary["zero_outcome_confirmed"] is True
    assert summary["customer_recovery_received"] == "0"
    assert summary["our_payment_received"] == "0"


def test_completion_event_rejects_float_money_and_cross_tenant_case(tmp_path):
    repo, client = make_client(tmp_path)
    save_case(repo, tenant="tenant-a")
    client.post(
        "/api/capacity/engagements",
        headers=headers("tenant-a", "create-engagement"),
        json=engagement_payload(),
    )

    bad_money = client.post(
        "/api/capacity/engagements/eng-1/events",
        headers=headers("tenant-a", "record-event"),
        json=event_payload(
            "float",
            "OUR_PAYMENT_RECEIVED",
            case_id=None,
            amount=3500.0,
            currency="EUR",
        ),
    )
    assert bad_money.status_code == 400
    assert "exact decimal" in bad_money.get_json()["detail"]

    client.post(
        "/api/capacity/engagements",
        headers=headers("tenant-b", "create-engagement"),
        json=engagement_payload(),
    )
    foreign = client.post(
        "/api/capacity/engagements/eng-1/events",
        headers=headers("tenant-b", "record-event"),
        json=event_payload("foreign", "CASE_LINKED"),
    )
    assert foreign.status_code == 404


def test_completion_case_draft_exposes_missing_inputs_not_fake_case(tmp_path):
    _repo, client = make_client(tmp_path)
    response = client.get(
        "/api/capacity/evidence/case-draft?company_id=supplier-1",
        headers=headers(),
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["ready_for_human_case_creation"] is False
    assert "ACTUAL_UNITS" in body["missing_required"]
    assert body["truth_rule"].endswith("not an entitlement decision")


def test_completion_unknown_fields_fail_closed(tmp_path):
    _repo, client = make_client(tmp_path)
    payload = engagement_payload()
    payload["paid"] = True
    response = client.post(
        "/api/capacity/engagements",
        headers=headers(intent="create-engagement"),
        json=payload,
    )
    assert response.status_code == 400
    assert "unknown request fields" in response.get_json()["detail"]
