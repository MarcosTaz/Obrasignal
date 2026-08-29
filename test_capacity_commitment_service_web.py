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


def seed_scope(repo, client, *, tenant="tenant-a"):
    repo.save(
        AssistedCaseState(
            tenant_id=tenant,
            company_id="supplier-1",
            customer_id="oem-1",
            program_id="program-1",
            recovery_case=case("case-1", currency="EUR"),
            evidence_refs=("contract:1",),
            contract_id="lta-1",
            deadline="2099-09-30",
        )
    )
    response = client.post(
        "/api/capacity/engagements",
        headers=headers(tenant, "create-engagement"),
        json={
            "engagement_id": "eng-1",
            "company_id": "supplier-1",
            "customer_id": "oem-1",
            "program_id": "program-1",
            "currency": "EUR",
        },
    )
    assert response.status_code == 201


def test_monitoring_requires_intent_and_is_tenant_scoped(tmp_path):
    repo, client = make_client(tmp_path)
    seed_scope(repo, client)
    payload = {
        "monitor_id": "monitor-v1",
        "engagement_id": "eng-1",
        "case_id": "case-1",
        "cadence_days": 30,
        "next_check_on": "2026-09-30",
    }
    denied = client.post("/api/capacity/monitoring", headers=headers(), json=payload)
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "monitor_intent_required"

    created = client.post(
        "/api/capacity/monitoring",
        headers=headers(intent="create-monitor"),
        json=payload,
    )
    assert created.status_code == 201
    assert created.get_json()["monitor"]["cadence_days"] == 30

    own = client.get("/api/capacity/monitoring", headers=headers("tenant-a"))
    other = client.get("/api/capacity/monitoring", headers=headers("tenant-b"))
    assert own.get_json()["count"] == 1
    assert other.get_json()["count"] == 0


def test_monitor_supersession_exposes_only_active_plan(tmp_path):
    repo, client = make_client(tmp_path)
    seed_scope(repo, client)
    first = {
        "monitor_id": "monitor-v1",
        "engagement_id": "eng-1",
        "case_id": "case-1",
        "cadence_days": 30,
        "next_check_on": "2026-09-30",
    }
    second = {
        "monitor_id": "monitor-v2",
        "engagement_id": "eng-1",
        "case_id": "case-1",
        "cadence_days": 14,
        "next_check_on": "2026-09-14",
        "supersedes_monitor_id": "monitor-v1",
    }
    for payload in (first, second):
        assert client.post(
            "/api/capacity/monitoring",
            headers=headers(intent="create-monitor"),
            json=payload,
        ).status_code == 201
    listing = client.get("/api/capacity/monitoring", headers=headers()).get_json()
    assert listing["count"] == 1
    assert listing["items"][0]["monitor_id"] == "monitor-v2"


def test_support_ticket_and_event_resolve_reopen_over_http(tmp_path):
    repo, client = make_client(tmp_path)
    seed_scope(repo, client)
    opened = client.post(
        "/api/capacity/support",
        headers=headers(intent="open-support"),
        json={
            "ticket_id": "ticket-1",
            "engagement_id": "eng-1",
            "case_id": "case-1",
            "category": "CALCULATION",
            "summary": "Explain the mitigation line",
            "opened_at": "2026-08-29T20:00:00Z",
        },
    )
    assert opened.status_code == 201
    assert opened.get_json()["ticket"]["status"] == "OPEN"

    resolved = client.post(
        "/api/capacity/support/ticket-1/events",
        headers=headers(intent="record-support-event"),
        json={
            "support_event_id": "support-1",
            "event_type": "RESOLVED",
            "occurred_at": "2026-08-29T21:00:00Z",
            "note": "Reviewed source evidence",
        },
    )
    assert resolved.status_code == 201
    assert resolved.get_json()["state"]["status"] == "RESOLVED"

    reopened = client.post(
        "/api/capacity/support/ticket-1/events",
        headers=headers(intent="record-support-event"),
        json={
            "support_event_id": "support-2",
            "event_type": "REOPENED",
            "occurred_at": "2026-08-30T09:00:00Z",
            "note": "New amendment received",
        },
    )
    assert reopened.status_code == 201
    assert reopened.get_json()["state"]["status"] == "OPEN"
    detail = client.get("/api/capacity/support/ticket-1", headers=headers()).get_json()
    assert detail["ticket"]["event_count"] == 2


def test_support_cross_tenant_is_hidden(tmp_path):
    repo, client = make_client(tmp_path)
    seed_scope(repo, client)
    client.post(
        "/api/capacity/support",
        headers=headers(intent="open-support"),
        json={
            "ticket_id": "ticket-1",
            "engagement_id": "eng-1",
            "category": "OTHER",
            "summary": "Question",
            "opened_at": "2026-08-29T20:00:00Z",
        },
    )
    response = client.get("/api/capacity/support/ticket-1", headers=headers("tenant-b"))
    assert response.status_code == 404


def test_observability_reports_technical_truth_without_commercial_false_green(tmp_path):
    repo, client = make_client(tmp_path)
    seed_scope(repo, client)
    response = client.get("/api/capacity/observability", headers=headers())
    assert response.status_code == 200
    body = response.get_json()
    assert body["tenant_scoped"] is True
    assert body["case_count"] == 1
    assert body["engagement_count"] == 1
    assert body["technical_ready"] is True
    assert body["commercial_ready"] is False
    assert "no buyer-qualified real case yet" in body["commercial_ready_blockers"]
    assert "no Capacity-specific payment processor/account verified" in body["commercial_ready_blockers"]


def test_service_routes_reject_unknown_fields_and_bad_cadence_type(tmp_path):
    repo, client = make_client(tmp_path)
    seed_scope(repo, client)
    bad = client.post(
        "/api/capacity/monitoring",
        headers=headers(intent="create-monitor"),
        json={
            "monitor_id": "m1",
            "engagement_id": "eng-1",
            "case_id": "case-1",
            "cadence_days": "30",
            "next_check_on": "2026-09-30",
        },
    )
    assert bad.status_code == 400
    assert "integer" in bad.get_json()["detail"]

    unknown = client.post(
        "/api/capacity/support",
        headers=headers(intent="open-support"),
        json={
            "ticket_id": "ticket-1",
            "engagement_id": "eng-1",
            "category": "OTHER",
            "summary": "Question",
            "opened_at": "2026-08-29T20:00:00Z",
            "resolved": True,
        },
    )
    assert unknown.status_code == 400
    assert "unknown request fields" in unknown.get_json()["detail"]
