from datetime import datetime, timezone

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
    exported["nodes"][0]["locator"]["field"] = "presentation-only"
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
