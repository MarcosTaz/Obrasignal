import json
from pathlib import Path

import data_lineage
import funnel_integration


ROOT = Path(__file__).resolve().parents[1]


def _evaluation():
    return {
        "profile_score": 77,
        "lot_score": 71,
        "lot_id": "lot-1",
        "match": True,
        "geography": {"score": 10, "reason": "fixture"},
        "commercial": {"score": 60},
        "economic_fit": {"status": "UNKNOWN"},
        "capability": {"status": "KNOWN"},
        "capability_evidence": [],
        "cpv_evidence": [],
        "hard_capability_blockers": [],
        "explanation": {"factors": []},
        "decision": "REVIEW",
        "reason": "fixture",
    }


def test_profile_fingerprint_is_deterministic_and_detects_input_drift():
    a = {"account_id": "acct-a", "keywords": ["avac"], "min_value": 1000}
    same = {"min_value": 1000, "keywords": ["avac"], "account_id": "acct-a"}
    changed = {"account_id": "acct-a", "keywords": ["avac", "climatizacao"], "min_value": 1000}

    assert data_lineage.canonical_fingerprint(a) == data_lineage.canonical_fingerprint(same)
    assert data_lineage.canonical_fingerprint(a) != data_lineage.canonical_fingerprint(changed)


def test_profile_lineage_is_hash_only_not_private_snapshot():
    profile = {
        "account_id": "acct-a",
        "name": "Private Company Name",
        "keywords": ["private-service"],
    }
    lineage = data_lineage.decision_profile_lineage(profile)

    assert lineage["reconstruction"] == "FINGERPRINT_ONLY"
    assert lineage["privacy_class"] == "HASHED_DERIVATION_METADATA"
    assert lineage["fingerprint"].startswith("sha256:")
    assert "Private Company Name" not in json.dumps(lineage)
    assert "private-service" not in json.dumps(lineage)


def test_persist_and_classify_attaches_exact_profile_fingerprint(monkeypatch):
    profile = {
        "account_id": "acct-a",
        "keywords": ["avac"],
        "countries": ["PRT"],
    }
    captured = {}

    monkeypatch.setattr(funnel_integration, "load_profile", lambda account_id: dict(profile))
    monkeypatch.setattr(funnel_integration, "evaluate_row", lambda enriched, profile: _evaluation())

    def fake_record(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(funnel_integration, "record_decision", fake_record)

    result = funnel_integration.persist_and_classify(
        None,
        {"source": "TED", "external_id": "notice-123"},
        True,
        account_id="acct-a",
    )

    assert result == ("REVIEW", "fixture")
    lineage = captured["features"]["lineage"]["profile"]
    assert lineage["fingerprint"] == data_lineage.canonical_fingerprint(profile)
    assert captured["rule_version"] == funnel_integration.RULE_VERSION
    assert captured["account_id"] == "acct-a"


def test_registry_is_fail_closed_and_marks_current_broken_edges():
    registry = json.loads((ROOT / "data_lineage_manifest.json").read_text(encoding="utf-8"))
    allowed = set(registry["status_vocabulary"])

    assert registry["mode"] == "observation_only"
    assert registry["canonical_main_sha"] == "66d43f6fd51cf9cea08016dad335aaa04b711a24"
    assert all(item["lineage_status"] in allowed for item in registry["data_elements"])

    edges = {(edge["from"], edge["to"]): edge for edge in registry["edges"]}
    profile_edge = edges[("company_profile.current", "opportunity_decision.account_scoped")]
    event_edge = edges[("opportunity_decision.account_scoped", "opportunity_event.new_high_match")]

    assert profile_edge["canonical_main_status"] == "BROKEN"
    assert "fingerprint-only" in profile_edge["candidate_repair"].lower()
    assert event_edge["canonical_main_status"] == "BROKEN"
    assert event_edge["candidate_repair"] == "OTHER_OWNER_REQUIRED"
