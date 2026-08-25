from datetime import datetime, timedelta, timezone

import pytest

from economic_fit import evaluate_economic_fit
from evidence_graph import EvidenceGraph, NodeType, Provenance, economic_fit_lineage


NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def test_node_content_is_snapshot_immutable_and_export_is_detached():
    locator = {"field": "deadline", "path": {"page": 2}}
    evidence_value = {"deadline": "2026-09-12", "lots": [1, 2]}
    metadata = {"method_inputs": {"rate": 0.35}}
    claim_value = {"cost": 126, "components": [180, 0.35]}

    provenance = Provenance(
        source="TED",
        external_id="immutable-1",
        published_at=NOW.isoformat(),
        locator=locator,
    )
    graph = EvidenceGraph("company-a")
    evidence_id = graph.add_evidence(provenance, evidence_value, field_name="payload")
    claim_id = graph.add_claim(
        NodeType.ESTIMATE,
        "immutable-1",
        "travel_cost",
        claim_value,
        metadata=metadata,
    )

    # Mutating caller-owned inputs after insertion must not rewrite audit history.
    locator["field"] = "tampered"
    locator["path"]["page"] = 99
    evidence_value["deadline"] = "2099-01-01"
    evidence_value["lots"].append(999)
    metadata["method_inputs"]["rate"] = 999
    claim_value["cost"] = 999
    claim_value["components"].append(999)

    evidence = graph.nodes[evidence_id]
    claim = graph.nodes[claim_id]
    assert evidence.provenance.locator["field"] == "deadline"
    assert evidence.provenance.locator["path"]["page"] == 2
    assert evidence.value["deadline"] == "2026-09-12"
    assert evidence.value["lots"] == (1, 2)
    assert claim.metadata["method_inputs"]["rate"] == 0.35
    assert claim.value["cost"] == 126
    assert claim.value["components"] == (180, 0.35)

    with pytest.raises(TypeError):
        evidence.provenance.locator["field"] = "tampered"
    with pytest.raises(TypeError):
        claim.metadata["method_inputs"]["rate"] = 1

    exported = graph.export()
    exported_evidence = next(node for node in exported["nodes"] if node["node_type"] == "EVIDENCE")
    exported_evidence["locator"]["field"] = "presentation-only"
    assert evidence.provenance.locator["field"] == "deadline"


def test_economic_fit_lineage_includes_deadline_procedure_and_profile_rules():
    signal = {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "econ-hardening",
        "value": "250000",
        "deadline": "2026-09-15",
        "procedure_type": "OPEN",
        "published_at": NOW.isoformat(),
        "source_updated_at": NOW.isoformat(),
        "url": "https://example.invalid/econ-hardening",
    }
    profile = {
        "min_value": 100000,
        "max_value": 500000,
        "min_deadline_days": 5,
        "max_deadline_days": 60,
        "economic_min_score": 60,
        "preferred_procedure_types": ["OPEN"],
        "excluded_procedure_types": ["NEGOTIATED"],
    }
    result = evaluate_economic_fit(signal["value"], profile=profile, opportunity=signal, today=NOW.date())
    graph = EvidenceGraph("company-a")
    inference_id = economic_fit_lineage(graph, signal, profile, result)
    explanation = graph.explain(inference_id, as_of=NOW)

    fact_predicates = {item["predicate"] for item in explanation["facts"]}
    assumption_predicates = {item["predicate"] for item in explanation["assumptions"]}

    assert {"value", "deadline", "procedure_type"} <= fact_predicates
    assert {
        "company_rule.min_value",
        "company_rule.max_value",
        "company_rule.min_deadline_days",
        "company_rule.max_deadline_days",
        "company_rule.economic_min_score",
        "company_rule.preferred_procedure_types",
        "company_rule.excluded_procedure_types",
    } <= assumption_predicates
    assert len(explanation["evidence"]) == 3
    assert explanation["estimates"][0]["metadata"]["rules"] == result["rules"]


def test_economic_fit_lineage_represents_missing_material_deadline_explicitly():
    signal = {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "econ-missing-deadline",
        "value": "250000",
        "published_at": NOW.isoformat(),
    }
    profile = {"min_deadline_days": 5}
    result = evaluate_economic_fit(signal["value"], profile=profile, opportunity=signal, today=NOW.date())
    graph = EvidenceGraph("company-a")
    inference_id = economic_fit_lineage(graph, signal, profile, result)
    explanation = graph.explain(inference_id, as_of=NOW)

    deadline = next(item for item in explanation["facts"] if item["predicate"] == "deadline")
    assert deadline["value"] is None
    assert deadline["metadata"]["missing"] is True


def test_blank_tenant_fails_closed():
    for tenant in ("", "   ", None):
        with pytest.raises(ValueError, match="tenant_id"):
            EvidenceGraph(tenant)


def test_retrieval_time_cannot_launder_unknown_publisher_freshness():
    graph = EvidenceGraph("company-a")
    provenance = Provenance(
        source="TED",
        external_id="freshness-unknown",
        retrieved_at=NOW.isoformat(),
    )
    evidence_id = graph.add_evidence(provenance, "Buyer", field_name="buyer")
    fact_id = graph.add_claim("FACT", "freshness-unknown", "buyer", "Buyer")
    graph.add_edge(evidence_id, fact_id, "SUPPORTS")

    explanation = graph.explain(fact_id, as_of=NOW)
    assert explanation["status"] == "SUPPORTED"
    assert explanation["confidence"] != "HIGH"
    assert explanation["evidence"][0]["stale"] is None
    assert "source_freshness" in explanation["missing"]


def test_future_publisher_timestamp_is_unknown_freshness_not_false_fresh():
    graph = EvidenceGraph("company-a")
    provenance = Provenance(
        source="TED",
        external_id="future-time",
        published_at=(NOW + timedelta(days=1)).isoformat(),
        retrieved_at=NOW.isoformat(),
    )
    evidence_id = graph.add_evidence(provenance, 10, field_name="value")
    fact_id = graph.add_claim("FACT", "future-time", "value", 10)
    graph.add_edge(evidence_id, fact_id, "SUPPORTS")

    explanation = graph.explain(fact_id, as_of=NOW)
    assert explanation["evidence"][0]["stale"] is None
    assert "source_freshness" in explanation["missing"]


def test_publisher_revision_is_distinct_but_retrieval_retry_does_not_inflate_evidence():
    graph = EvidenceGraph("company-a")
    first = Provenance(
        source="TED",
        external_id="revision-1",
        published_at="2026-08-20T00:00:00+00:00",
        effective_at="2026-08-20T00:00:00+00:00",
        retrieved_at="2026-08-20T01:00:00+00:00",
        raw_identifier="revision-1",
        locator={"field": "buyer"},
    )
    revised = Provenance(
        source="TED",
        external_id="revision-1",
        published_at="2026-08-20T00:00:00+00:00",
        effective_at="2026-08-21T00:00:00+00:00",
        retrieved_at="2026-08-21T01:00:00+00:00",
        raw_identifier="revision-1",
        locator={"field": "buyer"},
    )
    retry = Provenance(
        source="TED",
        external_id="revision-1",
        published_at="2026-08-20T00:00:00+00:00",
        effective_at="2026-08-21T00:00:00+00:00",
        retrieved_at="2026-08-25T00:00:00+00:00",
        raw_identifier="revision-1",
        locator={"field": "buyer"},
    )

    first_id = graph.add_evidence(first, "Buyer", field_name="buyer")
    revised_id = graph.add_evidence(revised, "Buyer", field_name="buyer")
    retry_id = graph.add_evidence(retry, "Buyer", field_name="buyer")

    assert revised_id != first_id
    assert retry_id == revised_id
    assert len(graph.nodes) == 2


def test_malformed_provenance_timestamp_fails_closed():
    with pytest.raises(ValueError, match="published_at"):
        Provenance(source="TED", external_id="bad-time", published_at="not-a-time")


def test_graph_execution_limits_fail_closed_without_corrupting_existing_state():
    graph = EvidenceGraph("company-a", max_nodes=2, max_edges=1)
    a = graph.add_claim("FACT", "a", "value", 1)
    b = graph.add_claim("FACT", "b", "value", 2)
    graph.add_edge(a, b, "DERIVED_FROM")

    with pytest.raises(ValueError, match="node limit"):
        graph.add_claim("FACT", "c", "value", 3)
    with pytest.raises(ValueError, match="edge limit"):
        graph.add_edge(b, a, "CONTRADICTS")

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
