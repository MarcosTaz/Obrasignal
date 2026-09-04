from decimal import Decimal
import sqlite3

import pytest

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
from factories.capacity_commitment.evidence_graph import build_case_evidence_graph
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.workflow import Engagement, WorkflowEvent, WorkflowEventType, WorkflowRepository


def seed_source_and_facts(db_path):
    repo = EvidenceRepository(str(db_path))
    repo.save_source(
        EvidenceSource(
            tenant_id="tenant-a",
            evidence_id="contract-1",
            kind=EvidenceKind.CONTRACT,
            display_name="LTA.pdf",
            external_ref="data-room:lta-1",
            sha256=sha256_bytes(b"synthetic lta"),
            captured_at="2026-09-04T10:00:00Z",
        )
    )
    raw = [
        ("customer", FactType.CUSTOMER_ID, "oem-1", None),
        ("program", FactType.PROGRAM_ID, "program-1", None),
        ("contract", FactType.CONTRACT_ID, "lta-1", None),
        ("period", FactType.PERIOD_ID, "2026Q2", None),
        ("currency", FactType.CURRENCY, "EUR", None),
        ("unit", FactType.UNIT, "parts", None),
        ("commitment-state", FactType.COMMITMENT_STATE, "FIRM", None),
        ("committed", FactType.COMMITTED_UNITS, "100000", None),
        ("actual", FactType.ACTUAL_UNITS, "70000", "shipments:q2"),
        ("cost", FactType.DEDICATED_COST, "1200000", None),
        ("basis", FactType.AMORTIZATION_BASIS_UNITS, "100000", None),
        ("mitigation", FactType.MITIGATION, "0", None),
        ("prior", FactType.PRIOR_PAYMENT, "0", None),
        ("right", FactType.EXPLICIT_RECOVERY_RIGHT, "true", None),
        ("notice", FactType.NOTICE_VALID, "true", None),
        ("deadline", FactType.DEADLINE, "2026-12-31", None),
    ]
    for fact_id, fact_type, value, scope in raw:
        repo.save_fact(
            ExtractedFact(
                tenant_id="tenant-a",
                fact_id=fact_id,
                evidence_id="contract-1",
                fact_type=fact_type,
                raw_value=value,
                normalized_value=value,
                scope_ref=scope,
                page_ref="p.12",
                clause_ref="4.2",
                review_state=ReviewState.UNREVIEWED,
            )
        )
        repo.review_fact(tenant_id="tenant-a", fact_id=fact_id, decision=ReviewState.CONFIRMED)
    return repo


def controls():
    return HumanCaseControls(
        evidence_supported=True,
        asset_dedicated=True,
        already_fully_amortized=False,
        already_paid=False,
        exposure_type=ExposureType.DEDICATED_CAPEX,
        cost_recovery_mode=CostRecoveryMode.UNIT_AMORTIZED,
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


def setup_case(tmp_path):
    db = tmp_path / "capacity.db"
    capacity = CapacityRepository(str(db))
    evidence = seed_source_and_facts(db)
    state = build_state_from_confirmed_evidence(
        tenant_id="tenant-a",
        company_id="supplier-1",
        case_id="case-1",
        facts=evidence.list_facts(tenant_id="tenant-a"),
        controls=controls(),
    )
    capacity.save(state)
    return db, capacity, state


def node_map(graph):
    return {item.node_id: item for item in graph.nodes}


def edge_set(graph):
    return {(item.from_node, item.to_node, item.relation) for item in graph.edges}


def test_graph_traces_hash_clause_reviewed_fact_case_and_engine_result(tmp_path):
    _db, capacity, state = setup_case(tmp_path)
    graph = build_case_evidence_graph(capacity, tenant_id="tenant-a", case_id="case-1")
    nodes = node_map(graph)
    edges = edge_set(graph)

    assert graph.fact_provenance_complete is True
    assert set(state.fact_refs) >= {"committed", "actual", "right", "deadline"}
    assert nodes["source:contract-1"].attributes["sha256"] == sha256_bytes(b"synthetic lta")
    assert nodes["fact:committed"].attributes["clause_ref"] == "4.2"
    assert nodes["fact:committed"].attributes["normalized_value"] == "100000"
    assert ("source:contract-1", "fact:committed", "CONTAINS_REVIEWED_FACT") in edges
    assert ("fact:committed", "case:case-1", "FROZEN_INPUT_TO") in edges
    assert ("case:case-1", "result:case-1", "EVALUATED_AS") in edges
    result = nodes["result:case-1"].attributes
    assert result["claimable_amount"] == "360000"
    assert result["verified_recovery"] is False
    assert result["payment_received"] is False


def test_graph_includes_action_customer_recovery_invoice_and_our_payment_as_distinct_events(tmp_path):
    _db, capacity, _state = setup_case(tmp_path)
    workflow = WorkflowRepository(capacity.db_path)
    workflow.save_engagement(Engagement("tenant-a", "eng-1", "supplier-1", "oem-1", "program-1", "EUR"))
    events = [
        WorkflowEvent("tenant-a", "link", "eng-1", WorkflowEventType.CASE_LINKED, "2026-09-04T11:00:00Z", case_id="case-1"),
        WorkflowEvent("tenant-a", "action", "eng-1", WorkflowEventType.ACTION_SUBMITTED, "2026-09-04T12:00:00Z", case_id="case-1"),
        WorkflowEvent("tenant-a", "recovery", "eng-1", WorkflowEventType.CUSTOMER_RECOVERY_RECEIVED, "2026-09-05T12:00:00Z", case_id="case-1", amount=Decimal("100000"), currency="EUR"),
        WorkflowEvent("tenant-a", "invoice", "eng-1", WorkflowEventType.OUR_INVOICE_ISSUED, "2026-09-05T13:00:00Z", amount=Decimal("3500"), currency="EUR"),
        WorkflowEvent("tenant-a", "payment", "eng-1", WorkflowEventType.OUR_PAYMENT_RECEIVED, "2026-09-06T13:00:00Z", amount=Decimal("3500"), currency="EUR"),
    ]
    for item in events:
        workflow.append_event(item)

    graph = build_case_evidence_graph(capacity, tenant_id="tenant-a", case_id="case-1")
    nodes = node_map(graph)
    assert nodes["event:recovery"].attributes["event_type"] == "CUSTOMER_RECOVERY_RECEIVED"
    assert nodes["event:recovery"].attributes["amount"] == "100000"
    assert nodes["event:invoice"].attributes["event_type"] == "OUR_INVOICE_ISSUED"
    assert nodes["event:payment"].attributes["event_type"] == "OUR_PAYMENT_RECEIVED"
    assert nodes["event:payment"].attributes["amount"] == "3500"


def test_graph_fails_closed_if_frozen_fact_is_later_corrupted_to_rejected(tmp_path):
    db, capacity, _state = setup_case(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE capacity_commitment_evidence_facts SET review_state='REJECTED' WHERE tenant_id='tenant-a' AND fact_id='committed'"
        )
    with pytest.raises(RuntimeError, match="non-CONFIRMED"):
        build_case_evidence_graph(capacity, tenant_id="tenant-a", case_id="case-1")


def test_historical_case_without_fact_refs_is_marked_incomplete_not_fabricated(tmp_path):
    db = tmp_path / "capacity.db"
    capacity = CapacityRepository(str(db))
    evidence = EvidenceRepository(str(db))
    evidence.save_source(
        EvidenceSource(
            tenant_id="tenant-a",
            evidence_id="legacy-source",
            kind=EvidenceKind.CONTRACT,
            display_name="legacy.pdf",
            external_ref="archive:legacy",
            sha256=sha256_bytes(b"legacy synthetic"),
            captured_at="2026-01-01T00:00:00Z",
        )
    )
    capacity.save(
        AssistedCaseState(
            tenant_id="tenant-a",
            company_id="supplier-1",
            customer_id="oem-1",
            program_id="program-1",
            period_id="2026Q1",
            unit="parts",
            recovery_case=case("legacy"),
            evidence_refs=("legacy-source",),
            fact_refs=(),
            contract_id="lta-legacy",
            deadline="2099-12-31",
        )
    )
    graph = build_case_evidence_graph(capacity, tenant_id="tenant-a", case_id="legacy")
    assert graph.fact_provenance_complete is False
    assert not any(node.node_type == "REVIEWED_FACT" for node in graph.nodes)
