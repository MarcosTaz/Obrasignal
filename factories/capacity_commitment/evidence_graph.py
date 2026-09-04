from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .evidence import EvidenceRepository, ReviewState
from .repository import CapacityRepository
from .service import process_state
from .workflow import WorkflowRepository


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    attributes: Mapping[str, object]


@dataclass(frozen=True)
class GraphEdge:
    from_node: str
    to_node: str
    relation: str


@dataclass(frozen=True)
class CaseEvidenceGraph:
    case_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    fact_provenance_complete: bool


def _node(node_id: str, node_type: str, **attributes) -> GraphNode:
    return GraphNode(node_id=node_id, node_type=node_type, attributes=dict(sorted(attributes.items())))


def build_case_evidence_graph(
    repository: CapacityRepository,
    *,
    tenant_id: str,
    case_id: str,
) -> CaseEvidenceGraph:
    """Build a trace from source hashes and reviewed facts to case/result/actions.

    Historical snapshots without fact_refs are represented honestly as incomplete
    fact-level provenance. When fact_refs exist, every referenced fact must still be
    CONFIRMED, tenant-scoped and attached to one of the case's frozen evidence refs.
    """

    state = repository.load(tenant_id=tenant_id, case_id=case_id)
    processed = process_state(state)
    evidence_repo = EvidenceRepository(repository.db_path)
    workflow_repo = WorkflowRepository(repository.db_path)

    nodes: dict[str, GraphNode] = {}
    edges: set[tuple[str, str, str]] = set()

    case_node = f"case:{case_id}"
    result_node = f"result:{case_id}"
    nodes[case_node] = _node(
        case_node,
        "CASE",
        company_id=state.company_id,
        customer_id=state.customer_id,
        program_id=state.program_id,
        period_id=state.period_id,
        unit=state.unit,
        currency=state.recovery_case.currency.upper(),
        contract_id=state.contract_id,
        nomination_id=state.nomination_id,
    )
    result = processed.result
    nodes[result_node] = _node(
        result_node,
        "ENGINE_RESULT",
        engine_version=result.engine_version,
        recoverability_state=result.recoverability_state.value,
        shortfall_units=format(result.shortfall_units, "f"),
        economic_exposure=format(result.economic_exposure, "f"),
        mitigation=format(result.mitigation, "f"),
        prior_payment=format(result.prior_payment, "f"),
        net_exposure=format(result.net_exposure, "f"),
        claimable_amount=format(result.claimable_amount, "f"),
        reasons=list(result.reasons),
        verified_recovery=False,
        payment_received=False,
    )
    edges.add((case_node, result_node, "EVALUATED_AS"))

    frozen_sources = set(state.evidence_refs)
    for evidence_id in sorted(frozen_sources):
        source = evidence_repo.load_source(tenant_id=tenant_id, evidence_id=evidence_id)
        source_node = f"source:{evidence_id}"
        nodes[source_node] = _node(
            source_node,
            "EVIDENCE_SOURCE",
            evidence_id=source.evidence_id,
            kind=source.kind.value,
            display_name=source.display_name,
            external_ref=source.external_ref,
            sha256=source.sha256,
            captured_at=source.captured_at,
        )
        edges.add((source_node, case_node, "EVIDENCE_FOR"))

    fact_provenance_complete = bool(state.fact_refs)
    for fact_id in sorted(state.fact_refs):
        fact = evidence_repo.load_fact(tenant_id=tenant_id, fact_id=fact_id)
        if fact.review_state is not ReviewState.CONFIRMED:
            raise RuntimeError("case fact provenance references a non-CONFIRMED fact")
        if fact.evidence_id not in frozen_sources:
            raise RuntimeError("case fact provenance references evidence outside frozen case sources")
        fact_node = f"fact:{fact_id}"
        nodes[fact_node] = _node(
            fact_node,
            "REVIEWED_FACT",
            fact_id=fact.fact_id,
            evidence_id=fact.evidence_id,
            fact_type=fact.fact_type.value,
            normalized_value=fact.normalized_value,
            raw_value=fact.raw_value,
            scope_ref=fact.scope_ref,
            page_ref=fact.page_ref,
            clause_ref=fact.clause_ref,
            review_state=fact.review_state.value,
        )
        edges.add((f"source:{fact.evidence_id}", fact_node, "CONTAINS_REVIEWED_FACT"))
        edges.add((fact_node, case_node, "FROZEN_INPUT_TO"))

    for engagement in workflow_repo.list_engagements(tenant_id=tenant_id):
        events = workflow_repo.list_events(tenant_id=tenant_id, engagement_id=engagement.engagement_id)
        linked_to_case = any(event.case_id == case_id for event in events)
        if not linked_to_case:
            continue
        engagement_node = f"engagement:{engagement.engagement_id}"
        nodes[engagement_node] = _node(
            engagement_node,
            "ENGAGEMENT",
            engagement_id=engagement.engagement_id,
            company_id=engagement.company_id,
            customer_id=engagement.customer_id,
            program_id=engagement.program_id,
            currency=engagement.currency,
        )
        edges.add((case_node, engagement_node, "OPERATED_WITHIN"))
        for event in events:
            event_node = f"event:{event.event_id}"
            nodes[event_node] = _node(
                event_node,
                "WORKFLOW_EVENT",
                event_id=event.event_id,
                event_type=event.event_type.value,
                occurred_at=event.occurred_at,
                case_id=event.case_id,
                amount=None if event.amount is None else format(event.amount, "f"),
                currency=event.currency,
                external_ref=event.external_ref,
                note=event.note,
            )
            edges.add((engagement_node, event_node, "HAS_EVENT"))
            if event.case_id == case_id:
                edges.add((case_node, event_node, "CASE_EVENT"))

    return CaseEvidenceGraph(
        case_id=case_id,
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(GraphEdge(*item) for item in sorted(edges)),
        fact_provenance_complete=fact_provenance_complete,
    )
