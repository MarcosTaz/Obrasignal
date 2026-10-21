from datetime import datetime, timedelta, timezone

import pytest

from economic_fit import evaluate_economic_fit
from evidence_graph import (
    ClaimStatus,
    Confidence,
    EdgeType,
    EvidenceGraph,
    NodeType,
    Provenance,
    economic_fit_lineage,
    signal_to_fact,
)


NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def primary(source="TED", external_id="n1", **kw):
    return Provenance(
        source=source,
        external_id=external_id,
        source_url="https://example.invalid/notice",
        publisher="Official publisher",
        retrieved_at=kw.get("retrieved_at", NOW.isoformat()),
        published_at=kw.get("published_at", NOW.isoformat()),
        effective_at=kw.get("effective_at", NOW.isoformat()),
        raw_identifier=kw.get("raw_identifier", external_id),
        locator=kw.get("locator", {"field": "deadline"}),
    )


def test_fact_with_primary_evidence_and_provenance_preserved():
    g = EvidenceGraph("company-a")
    ev = g.add_evidence(primary(), "2026-09-12", field_name="deadline")
    fact = g.add_claim(NodeType.FACT, "n1", "deadline", "2026-09-12")
    g.add_edge(ev, fact, EdgeType.SUPPORTS)
    explanation = g.explain(fact, as_of=NOW)
    assert explanation["status"] == "SUPPORTED"
    assert explanation["confidence"] == "HIGH"
    assert explanation["evidence"][0]["publisher"] == "Official publisher"
    assert explanation["evidence"][0]["published_at"] == NOW.isoformat()
    assert explanation["evidence"][0]["locator"] == {"field": "deadline"}


def test_estimate_inference_and_assumption_lineage():
    g = EvidenceGraph("company-a")
    ev = g.add_evidence(primary(locator={"field": "distance_km"}), 180, field_name="distance_km", unit="km")
    fact = g.add_claim("FACT", "project", "distance_km", 180, unit="km")
    assumption = g.add_claim("ASSUMPTION", "company", "vehicle_cost_per_km", 0.35, unit="EUR/km")
    estimate = g.add_claim(
        "ESTIMATE",
        "project",
        "round_trip_cost",
        126,
        unit="EUR",
        method="2 * distance * cost_per_km",
        calculation_version="travel-v1",
    )
    inference = g.add_claim("INFERENCE", "project", "daily_commute_margin_pressure", True)
    g.add_edge(ev, fact, "SUPPORTS")
    g.add_edge(fact, estimate, "DERIVED_FROM")
    g.add_edge(assumption, estimate, "USES_ASSUMPTION")
    g.add_edge(estimate, inference, "DERIVED_FROM")
    explanation = g.explain(inference, as_of=NOW)
    assert explanation["facts"][0]["predicate"] == "distance_km"
    assert explanation["estimates"][0]["predicate"] == "round_trip_cost"
    assert explanation["assumptions"][0]["predicate"] == "vehicle_cost_per_km"
    assert estimate in explanation["dependencies"]


def test_conflicting_evidence_is_explicit():
    g = EvidenceGraph("a")
    ev1 = g.add_evidence(primary(external_id="a"), "2026-09-12", field_name="deadline")
    ev2 = g.add_evidence(primary(external_id="b"), "2026-09-15", field_name="deadline")
    a = g.add_claim("FACT", "project", "deadline", "2026-09-12")
    b = g.add_claim("FACT", "project", "deadline", "2026-09-15")
    g.add_edge(ev1, a, "SUPPORTS")
    g.add_edge(ev2, b, "SUPPORTS")
    g.add_edge(a, b, "CONTRADICTS")
    assert g.status(a, as_of=NOW) == ClaimStatus.CONFLICT
    assert g.status(b, as_of=NOW) == ClaimStatus.CONFLICT
    assert g.confidence(a, as_of=NOW) in {Confidence.MEDIUM, Confidence.LOW}


def test_stale_evidence_uses_source_time_not_retrieval_time():
    g = EvidenceGraph("a")
    old = NOW - timedelta(days=10)
    ev = g.add_evidence(
        primary(effective_at=old.isoformat(), published_at=old.isoformat(), retrieved_at=NOW.isoformat()),
        10,
        field_name="value",
    )
    fact = g.add_claim("FACT", "x", "value", 10)
    g.add_edge(ev, fact, "SUPPORTS")
    assert g.status(fact, as_of=NOW) == ClaimStatus.STALE


def test_missing_and_unsupported_are_not_false_or_zero():
    g = EvidenceGraph("a")
    missing = g.add_claim("FACT", "x", "deadline", None)
    unsupported = g.add_claim("FACT", "x", "buyer", "Buyer")
    assert g.status(missing, as_of=NOW) == ClaimStatus.UNKNOWN
    assert g.status(unsupported, as_of=NOW) == ClaimStatus.UNSUPPORTED
    assert g.confidence(unsupported, as_of=NOW) == Confidence.UNKNOWN


def test_duplicate_evidence_does_not_inflate_graph_or_confidence():
    g = EvidenceGraph("a")
    p = primary()
    one = g.add_evidence(p, 100, field_name="value")
    two = g.add_evidence(p, 100, field_name="value")
    assert one == two
    assert len(g.nodes) == 1


def test_supersession_preserves_history_and_marks_old_claim():
    g = EvidenceGraph("a")
    old = g.add_claim("FACT", "x", "deadline", "2026-09-12")
    new = g.add_claim("FACT", "x", "deadline", "2026-09-15")
    g.add_edge(new, old, "SUPERSEDES")
    assert g.status(old, as_of=NOW) == ClaimStatus.SUPERSEDED
    assert old not in g.ancestors(old)
    assert new not in g.ancestors(old)
    assert old in g.nodes and new in g.nodes


def test_cycle_detection_for_lineage():
    g = EvidenceGraph("a")
    a = g.add_claim("ASSUMPTION", "x", "a", 1)
    b = g.add_claim("ESTIMATE", "x", "b", 2)
    g.add_edge(a, b, "DERIVED_FROM")
    with pytest.raises(ValueError, match="cycle"):
        g.add_edge(b, a, "DERIVED_FROM")


def test_cycle_detection_for_supersession():
    g = EvidenceGraph("a")
    old = g.add_claim("FACT", "x", "deadline", "2026-09-12")
    new = g.add_claim("FACT", "x", "deadline", "2026-09-15")
    g.add_edge(new, old, "SUPERSEDES")
    with pytest.raises(ValueError, match="cycle"):
        g.add_edge(old, new, "SUPERSEDES")


def test_tenant_isolation():
    a = EvidenceGraph("company-a")
    b = EvidenceGraph("company-b")
    node_a = a.add_claim("FACT", "x", "v", 1)
    node_b = b.add_claim("FACT", "x", "v", 1)
    assert node_a != node_b
    with pytest.raises(KeyError):
        a.add_edge(node_a, node_b, "DERIVED_FROM")


def test_deterministic_graph_export_and_ids():
    def build():
        g = EvidenceGraph("a")
        ev = g.add_evidence(primary(), 100, field_name="value")
        fact = g.add_claim("FACT", "n1", "value", 100)
        g.add_edge(ev, fact, "SUPPORTS")
        return g.export()

    assert build() == build()


def test_generic_signal_adapter_preserves_source_timestamps():
    g = EvidenceGraph("a")
    signal = {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "abc",
        "deadline": "2026-09-01",
        "published_at": "2026-08-24T12:00:00+00:00",
        "source_updated_at": "2026-08-24T14:00:00+00:00",
        "last_observed": "2026-08-25T00:00:00+00:00",
        "url": "https://example.invalid/abc",
        "source_reference": "notice-abc",
    }
    fact = signal_to_fact(g, signal, "deadline", publisher="TED")
    item = g.explain(fact, as_of=NOW)["evidence"][0]
    assert item["published_at"] == "2026-08-24T12:00:00+00:00"
    assert item["effective_at"] == "2026-08-24T14:00:00+00:00"
    assert item["retrieved_at"] == "2026-08-25T00:00:00+00:00"


def test_economic_fit_full_chain_explains_decision_support():
    signal = {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "econ-1",
        "value": "250000",
        "published_at": NOW.isoformat(),
        "source_updated_at": NOW.isoformat(),
        "url": "https://example.invalid/econ-1",
    }
    profile = {"min_value": 100000, "max_value": 500000, "economic_min_score": 60}
    result = evaluate_economic_fit(signal["value"], profile=profile, opportunity=signal, today=NOW.date())
    g = EvidenceGraph("company-a")
    inference = economic_fit_lineage(g, signal, profile, result)
    explanation = g.explain(inference, as_of=NOW)
    assert explanation["claim"]["value"] == result["status"]
    assert explanation["facts"]
    assert explanation["estimates"]
    assert explanation["assumptions"]
    assert explanation["evidence"]
    assert explanation["claim"]["calculation_version"] == result["rule_version"]
    assert explanation["model_version"] == "evidence-graph-v1"
