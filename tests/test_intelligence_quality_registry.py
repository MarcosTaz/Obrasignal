import json
from pathlib import Path

from commercial_score_v2 import score_v2


REGISTRY = Path(__file__).resolve().parents[1] / "intelligence_quality_registry.json"


def _registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_registry_is_observation_only_and_exact_main_scoped():
    registry = _registry()

    assert registry["mode"] == "observation_only"
    assert registry["baseline_main_sha"] == "66d43f6fd51cf9cea08016dad335aaa04b711a24"
    assert registry["status_vocabulary"] == ["PROVEN", "PARTIAL", "UNKNOWN", "STALE", "REGRESSED"]


def test_registry_preserves_score_confidence_probability_boundaries():
    registry = _registry()
    principles = registry["principles"]
    confidence = registry["confidence_contract"]

    assert principles["score_is_probability"] is False
    assert principles["score_is_confidence"] is False
    assert confidence["calibrated_confidence_model_exists"] is False
    assert confidence["win_probability_model_exists"] is False
    assert confidence["allowed_claim"] == "data coverage/completeness proxy only"
    assert "probability of winning" in confidence["forbidden_claims"]


def test_current_commercial_confidence_is_field_coverage_not_fit_probability():
    complete = score_v2({
        "title": "Construção de pavilhão industrial",
        "description": "Empreitada de construção",
        "buyer": "Município",
        "cpv": "45213220",
        "deadline": "2099-12-31",
        "value_numeric": 250000,
        "procedure_type": "open procedure",
    })
    missing = score_v2({})

    assert complete["confidence"] == 100
    assert complete["missing_fields"] == []
    assert missing["confidence"] == 0
    assert set(missing["missing_fields"]) == {"cpv", "deadline", "procedure_type", "title/description", "value"}


def test_missing_information_is_never_registered_as_positive_or_negative_by_default():
    principles = _registry()["principles"]

    assert principles["missing_is_positive"] is False
    assert principles["missing_is_negative"] is False
    assert principles["unknown_may_be_coerced_to_relevant"] is False
    assert principles["unknown_may_be_coerced_to_actionable"] is False


def test_known_semantic_waits_have_explicit_reopen_conditions():
    waits = [item for item in _registry()["known_debt"] if item["status"] == "WAIT"]

    assert {item["issue"] for item in waits} == {471, 472}
    assert all(item.get("reopen") for item in waits)


def test_green_draft_evidence_is_head_specific_and_never_claims_merge():
    drafts = _registry()["safe_drafts"]

    assert {item["pr"] for item in drafts} == {458, 461, 466, 475}
    assert all(len(item["head"]) == 40 for item in drafts)
    assert all(item["exact_head_ci"] == "PROVEN" for item in drafts)
    assert all(item["merged"] is False for item in drafts)


def test_feature_inventory_names_current_legacy_score_contamination():
    features = {item["feature"]: item for item in _registry()["features"]}

    legacy = features["legacy_tender_score"]
    assert legacy["role"] == "must not become account-specific fit authority"
    assert legacy["status"] == "REGRESSED"
