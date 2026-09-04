import sqlite3
from decimal import Decimal

import pytest

from factories.capacity_commitment.application import create_completion_app
from factories.capacity_commitment.atomic_commit import commit_case_and_link
from factories.capacity_commitment.engine import CostRecoveryMode, ExposureType
from factories.capacity_commitment.evidence import (
    EvidenceKind,
    EvidenceRepository,
    EvidenceSource,
    ExtractedFact,
    FactType,
    ReviewState,
    sha256_bytes,
)
from factories.capacity_commitment.evidence_case import HumanCaseControls, build_state_from_confirmed_evidence
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.workflow import (
    Engagement,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowRepository,
)


def headers(tenant="tenant-a", intent=None):
    out = {"X-Test-Tenant": tenant}
    if intent:
        out["X-Capacity-Intent"] = intent
    return out


def source():
    return EvidenceSource(
        tenant_id="tenant-a",
        evidence_id="e1",
        kind=EvidenceKind.CONTRACT,
        display_name="synthetic-evidence.pdf",
        external_ref="synthetic:data-room:e1",
        sha256=sha256_bytes(b"synthetic evidence only"),
        captured_at="2026-09-04T12:00:00Z",
    )


def fact(fact_id, fact_type, value, *, scope_ref=None):
    return ExtractedFact(
        tenant_id="tenant-a",
        fact_id=fact_id,
        evidence_id="e1",
        fact_type=fact_type,
        raw_value=value,
        normalized_value=value,
        scope_ref=scope_ref,
        page_ref="p.1",
        clause_ref="1.1",
        review_state=ReviewState.UNREVIEWED,
    )


def seed_confirmed_evidence(db_path, *, customer="oem-1", include_right=True):
    repo = EvidenceRepository(str(db_path))
    repo.save_source(source())
    items = [
        fact("customer", FactType.CUSTOMER_ID, customer),
        fact("program", FactType.PROGRAM_ID, "program-1"),
        fact("contract", FactType.CONTRACT_ID, "lta-1"),
        fact("period", FactType.PERIOD_ID, "2026Q2"),
        fact("currency", FactType.CURRENCY, "EUR"),
        fact("unit", FactType.UNIT, "parts"),
        fact("state", FactType.COMMITMENT_STATE, "FIRM"),
        fact("committed", FactType.COMMITTED_UNITS, "100000"),
        fact("actual-a", FactType.ACTUAL_UNITS, "70000", scope_ref="ship-a"),
        fact("cost", FactType.DEDICATED_COST, "1200000"),
        fact("basis", FactType.AMORTIZATION_BASIS_UNITS, "100000"),
        fact("mitigation", FactType.MITIGATION, "0"),
        fact("prior", FactType.PRIOR_PAYMENT, "0"),
        fact("notice", FactType.NOTICE_VALID, "true"),
        fact("deadline", FactType.DEADLINE, "2026-12-31"),
    ]
    if include_right:
        items.append(fact("right", FactType.EXPLICIT_RECOVERY_RIGHT, "true"))
    for item in items:
        repo.save_fact(item)
        repo.review_fact(tenant_id="tenant-a", fact_id=item.fact_id, decision=ReviewState.CONFIRMED)
    return repo


def controls_json(**overrides):
    values = dict(
        evidence_supported=True,
        asset_dedicated=True,
        already_fully_amortized=False,
        already_paid=False,
        exposure_type="DEDICATED_CAPEX",
        cost_recovery_mode="UNIT_AMORTIZED",
        duplicate_claim=False,
        customer_matches=True,
        program_matches=True,
        period_matches=True,
        currency_matches=True,
        unit_matches=True,
        actuals_complete=True,
        actuals_deduplicated=True,
        cancelled_orders_excluded=True,
        amortization_verified=True,
        asset_dedication_verified=True,
        mitigation_reviewed=True,
        prior_recovery_reviewed=True,
        notice_window_verified=True,
        contract_matches=True,
        contract_current=True,
        amendment_reviewed=True,
        amendment_matches=True,
        duplicate_claim_reviewed=True,
    )
    values.update(overrides)
    return values


def controls_model():
    raw = controls_json()
    raw["exposure_type"] = ExposureType(raw["exposure_type"])
    raw["cost_recovery_mode"] = CostRecoveryMode(raw["cost_recovery_mode"])
    return HumanCaseControls(**raw)


def make_app(tmp_path):
    db = tmp_path / "capacity.db"
    repo = CapacityRepository(str(db))
    app = create_completion_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return db, repo, app.test_client()


def create_engagement(client):
    response = client.post(
        "/api/capacity/engagements",
        headers=headers(intent="create-engagement"),
        json={
            "engagement_id": "eng-1",
            "company_id": "supplier-1",
            "customer_id": "oem-1",
            "program_id": "program-1",
            "currency": "EUR",
        },
    )
    assert response.status_code == 201


def commit_payload(case_id="case-evidence-1"):
    return {
        "case_id": case_id,
        "occurred_at": "2026-09-04T13:00:00Z",
        "reviewer_ref": "operator:synthetic-reviewer",
        "review_note": "synthetic test review only",
        "controls": controls_json(),
    }


def test_reviewed_evidence_commit_requires_explicit_intent(tmp_path):
    db, _repo, client = make_app(tmp_path)
    seed_confirmed_evidence(db)
    create_engagement(client)
    response = client.post(
        "/api/capacity/engagements/eng-1/cases/from-evidence",
        headers=headers(),
        json=commit_payload(),
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "reviewed_evidence_commit_intent_required"


def test_reviewed_evidence_http_commit_is_source_backed_audited_and_idempotent(tmp_path):
    db, repo, client = make_app(tmp_path)
    seed_confirmed_evidence(db)
    create_engagement(client)
    url = "/api/capacity/engagements/eng-1/cases/from-evidence"
    first = client.post(url, headers=headers(intent="commit-reviewed-evidence-case"), json=commit_payload())
    assert first.status_code == 201
    body = first.get_json()
    assert body["created"] is True
    assert body["linked"] is True
    assert body["period_id"] == "2026Q2"
    assert body["unit"] == "parts"
    assert body["result"]["committed_units"] == "100000"
    assert body["result"]["actual_units"] == "70000"
    assert body["result"]["claimable_amount"] == "360000"
    assert body["result"]["verified_recovery"] is False
    assert body["result"]["payment_received"] is False

    stored = repo.load(tenant_id="tenant-a", case_id="case-evidence-1")
    assert stored.period_id == "2026Q2"
    assert stored.unit == "parts"
    assert stored.recovery_case.mitigation == Decimal("0")
    assert stored.recovery_case.prior_payment == Decimal("0")

    second = client.post(url, headers=headers(intent="commit-reviewed-evidence-case"), json=commit_payload())
    assert second.status_code == 200
    assert second.get_json()["created"] is False
    assert second.get_json()["linked"] is False

    detail = client.get("/api/capacity/engagements/eng-1", headers=headers()).get_json()
    links = [item for item in detail["events"] if item["event_type"] == "CASE_LINKED"]
    assert len(links) == 1
    assert links[0]["external_ref"] == "operator:synthetic-reviewer"


def test_engagement_identity_mismatch_blocks_before_case_persistence(tmp_path):
    db, repo, client = make_app(tmp_path)
    seed_confirmed_evidence(db, customer="different-oem")
    create_engagement(client)
    response = client.post(
        "/api/capacity/engagements/eng-1/cases/from-evidence",
        headers=headers(intent="commit-reviewed-evidence-case"),
        json=commit_payload("case-mismatch"),
    )
    assert response.status_code == 400
    assert "does not match engagement" in response.get_json()["detail"]
    with pytest.raises(KeyError):
        repo.load(tenant_id="tenant-a", case_id="case-mismatch")


def test_missing_entitlement_fact_remains_unknown_over_http(tmp_path):
    db, _repo, client = make_app(tmp_path)
    seed_confirmed_evidence(db, include_right=False)
    create_engagement(client)
    payload = commit_payload("case-unknown")
    payload["controls"]["notice_window_verified"] = False
    response = client.post(
        "/api/capacity/engagements/eng-1/cases/from-evidence",
        headers=headers(intent="commit-reviewed-evidence-case"),
        json=payload,
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["result"]["recoverability_state"] == "UNKNOWN"
    assert body["result"]["claimable_amount"] == "0"
    assert "source_fact:EXPLICIT_RECOVERY_RIGHT" in body["missing_evidence"]


def test_atomic_commit_rolls_back_new_case_when_orphan_link_collision_exists(tmp_path):
    db, repo, _client = make_app(tmp_path)
    evidence = seed_confirmed_evidence(db)
    WorkflowRepository(str(db)).save_engagement(
        Engagement("tenant-a", "eng-1", "supplier-1", "oem-1", "program-1", "EUR")
    )
    state = build_state_from_confirmed_evidence(
        tenant_id="tenant-a",
        company_id="supplier-1",
        case_id="case-rollback",
        facts=evidence.list_facts(tenant_id="tenant-a"),
        controls=controls_model(),
    )
    event = WorkflowEvent(
        tenant_id="tenant-a",
        event_id="case-rollback:linked",
        engagement_id="eng-1",
        event_type=WorkflowEventType.CASE_LINKED,
        occurred_at="2026-09-04T13:00:00Z",
        case_id="case-rollback",
        external_ref="operator:reviewer",
    )
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO capacity_commitment_workflow_events
            (tenant_id,event_id,engagement_id,event_type,occurred_at,case_id,amount,currency,external_ref,note,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "tenant-a",
                "case-rollback:linked",
                "eng-1",
                "CASE_LINKED",
                "2026-09-04T12:00:00Z",
                "case-rollback",
                None,
                None,
                "corrupt:orphan",
                None,
                "2026-09-04T12:00:00Z",
            ),
        )
    with pytest.raises(RuntimeError, match="orphan CASE_LINKED"):
        commit_case_and_link(db_path=str(db), state=state, engagement_id="eng-1", link_event=event)
    with pytest.raises(KeyError):
        repo.load(tenant_id="tenant-a", case_id="case-rollback")
