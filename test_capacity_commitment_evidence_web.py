from factories.capacity_commitment.evidence import sha256_bytes
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.web import create_app


def headers(tenant="tenant-a", intent=None):
    result = {"X-Test-Tenant": tenant}
    if intent:
        result["X-Capacity-Intent"] = intent
    return result


def source_payload(evidence_id="contract-1"):
    return {
        "evidence_id": evidence_id,
        "kind": "CONTRACT",
        "display_name": "LTA.pdf",
        "external_ref": f"customer-room:{evidence_id}",
        "sha256": sha256_bytes(evidence_id.encode()),
        "captured_at": "2026-08-29T20:00:00Z",
    }


def fact_payload(fact_id="committed", evidence_id="contract-1", **overrides):
    payload = {
        "fact_id": fact_id,
        "evidence_id": evidence_id,
        "fact_type": "COMMITTED_UNITS",
        "raw_value": "100,000 units",
        "normalized_value": "100000",
        "page_ref": "p.4",
        "clause_ref": "4.2",
    }
    payload.update(overrides)
    return payload


def make_client(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return app.test_client()


def test_evidence_source_requires_explicit_intent_and_is_tenant_scoped(tmp_path):
    client = make_client(tmp_path)
    denied = client.post(
        "/api/capacity/evidence/sources",
        headers=headers(),
        json=source_payload(),
    )
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "evidence_intent_required"

    created = client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=source_payload(),
    )
    assert created.status_code == 201
    assert created.get_json()["source"]["evidence_id"] == "contract-1"

    own = client.get("/api/capacity/evidence/sources", headers=headers("tenant-a"))
    other = client.get("/api/capacity/evidence/sources", headers=headers("tenant-b"))
    assert own.get_json()["count"] == 1
    assert other.get_json()["count"] == 0


def test_fact_is_unreviewed_until_explicit_human_review(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=source_payload(),
    )

    created = client.post(
        "/api/capacity/evidence/facts",
        headers=headers(intent="extract-fact"),
        json=fact_payload(),
    )
    assert created.status_code == 201
    assert created.get_json()["fact"]["review_state"] == "UNREVIEWED"

    before = client.get("/api/capacity/evidence/normalization", headers=headers())
    assert before.get_json()["singleton_values"] == {}

    reviewed = client.post(
        "/api/capacity/evidence/facts/committed/review",
        headers=headers(intent="review-fact"),
        json={"decision": "CONFIRMED"},
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["fact"]["review_state"] == "CONFIRMED"

    after = client.get("/api/capacity/evidence/normalization", headers=headers())
    assert after.get_json()["singleton_values"]["COMMITTED_UNITS"] == "100000"
    assert after.get_json()["truth_rule"].startswith("only CONFIRMED")


def test_cross_tenant_fact_attachment_and_review_fail_closed(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/capacity/evidence/sources",
        headers=headers("tenant-a", "connect-evidence"),
        json=source_payload(),
    )
    client.post(
        "/api/capacity/evidence/facts",
        headers=headers("tenant-a", "extract-fact"),
        json=fact_payload(),
    )

    foreign_create = client.post(
        "/api/capacity/evidence/facts",
        headers=headers("tenant-b", "extract-fact"),
        json=fact_payload(fact_id="foreign"),
    )
    assert foreign_create.status_code == 404

    foreign_review = client.post(
        "/api/capacity/evidence/facts/committed/review",
        headers=headers("tenant-b", "review-fact"),
        json={"decision": "CONFIRMED"},
    )
    assert foreign_review.status_code == 404


def test_evidence_payload_is_strict_and_cannot_self_mark_confirmed(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=source_payload(),
    )
    payload = fact_payload()
    payload["review_state"] = "CONFIRMED"
    response = client.post(
        "/api/capacity/evidence/facts",
        headers=headers(intent="extract-fact"),
        json=payload,
    )
    assert response.status_code == 400
    assert "unknown request fields" in response.get_json()["detail"]


def test_conflicting_confirmed_facts_are_exposed_not_silently_resolved(tmp_path):
    client = make_client(tmp_path)
    client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=source_payload(),
    )
    for fact_id, value in (("a", "100000"), ("b", "90000")):
        client.post(
            "/api/capacity/evidence/facts",
            headers=headers(intent="extract-fact"),
            json=fact_payload(fact_id=fact_id, normalized_value=value),
        )
        client.post(
            f"/api/capacity/evidence/facts/{fact_id}/review",
            headers=headers(intent="review-fact"),
            json={"decision": "CONFIRMED"},
        )

    normalized = client.get("/api/capacity/evidence/normalization", headers=headers()).get_json()
    assert normalized["conflict_free"] is False
    assert normalized["conflicts"] == ["conflicting confirmed COMMITTED_UNITS"]


def test_actual_rows_deduplicate_by_scope_and_never_double_count(tmp_path):
    client = make_client(tmp_path)
    source = source_payload("actuals")
    source["kind"] = "ACTUALS"
    client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=source,
    )
    for fact_id in ("row-1", "row-2"):
        response = client.post(
            "/api/capacity/evidence/facts",
            headers=headers(intent="extract-fact"),
            json=fact_payload(
                fact_id=fact_id,
                evidence_id="actuals",
                fact_type="ACTUAL_UNITS",
                raw_value="100",
                normalized_value="100",
                scope_ref="shipment-001",
            ),
        )
        assert response.status_code == 201
        client.post(
            f"/api/capacity/evidence/facts/{fact_id}/review",
            headers=headers(intent="review-fact"),
            json={"decision": "CONFIRMED"},
        )

    normalized = client.get("/api/capacity/evidence/normalization", headers=headers()).get_json()
    assert normalized["actual_units"] is None
    assert normalized["conflict_free"] is False
    assert normalized["conflicts"] == ["duplicate confirmed ACTUAL_UNITS scope shipment-001"]


def test_evidence_conflicts_return_specific_409_not_case_claim(tmp_path):
    client = make_client(tmp_path)
    first = source_payload()
    assert client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=first,
    ).status_code == 201
    changed = dict(first)
    changed["display_name"] = "different.pdf"
    response = client.post(
        "/api/capacity/evidence/sources",
        headers=headers(intent="connect-evidence"),
        json=changed,
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "evidence_source_conflict"
