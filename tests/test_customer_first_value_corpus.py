import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "customer_first_value_corpus.json"
FACTORY_TITLE = "Customer Journey, First Value & Outcome Integrity"
CANONICAL_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"
EXPECTED_SCENARIOS = {
    "GOOD_MATCH",
    "NO_MATCH",
    "INSUFFICIENT_INFORMATION",
    "STALE_SOURCE",
    "PARTIAL_COVERAGE",
    "CLOSED_OPPORTUNITY",
    "PROFILE_INCOMPLETE",
    "SYSTEM_FAILURE",
}


def _load():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_first_value_corpus_is_exact_factory_and_exact_canonical_head():
    corpus = _load()
    assert corpus["factory_title"] == FACTORY_TITLE
    assert corpus["canonical_main_sha"] == CANONICAL_MAIN
    assert {scenario["id"] for scenario in corpus["scenarios"]} == EXPECTED_SCENARIOS


def test_only_good_match_can_be_a_first_value_candidate():
    corpus = _load()
    candidates = {
        scenario["id"]
        for scenario in corpus["scenarios"]
        if scenario["expected_outcome"] == "FIRST_VALUE_CANDIDATE"
    }
    assert candidates == {"GOOD_MATCH"}


def test_transport_exposure_and_subscription_do_not_define_first_value():
    contract = _load()["first_value_candidate_contract"]
    insufficient = set(contract["not_sufficient_alone"])
    assert {
        "login",
        "radar_loaded",
        "first_shortlist_generated",
        "notification_sent",
        "alert_delivered",
        "notification_opened",
        "score_present",
        "subscription_active",
    }.issubset(insufficient)


def test_no_match_requires_explicitly_sufficient_current_coverage():
    scenarios = {scenario["id"]: scenario for scenario in _load()["scenarios"]}
    no_match = scenarios["NO_MATCH"]
    assert no_match["source_state"] == "CURRENT_SUFFICIENT_FOR_NO_MATCH_CLAIM"
    assert no_match["expected_outcome"] == "TRUTHFUL_NO_MATCH"
    assert "zero_market" in no_match["forbidden_claims"]


def test_unknown_stale_partial_and_system_failure_cannot_be_first_value():
    scenarios = {scenario["id"]: scenario for scenario in _load()["scenarios"]}
    for scenario_id in (
        "INSUFFICIENT_INFORMATION",
        "STALE_SOURCE",
        "PARTIAL_COVERAGE",
        "SYSTEM_FAILURE",
    ):
        scenario = scenarios[scenario_id]
        assert scenario["expected_outcome"] != "FIRST_VALUE_CANDIDATE"
    assert "first_value" in scenarios["INSUFFICIENT_INFORMATION"]["forbidden_claims"]
    assert "first_value_from_stale_empty" in scenarios["STALE_SOURCE"]["forbidden_claims"]
    assert "first_value_from_cached_or_failed_load" in scenarios["SYSTEM_FAILURE"]["forbidden_claims"]


def test_closed_opportunity_separates_relevance_from_current_actionability():
    scenarios = {scenario["id"]: scenario for scenario in _load()["scenarios"]}
    closed = scenarios["CLOSED_OPPORTUNITY"]
    assert closed["actionability_state"] == "NON_ACTIONABLE"
    assert closed["expected_outcome"] == "NO_LONGER_ACTIONABLE"
    assert "automatic_workflow_transition_permission" in closed["forbidden_claims"]
    assert "State Machine/Workflow" in closed["owner_dependencies"]


def test_profile_incomplete_requires_edit_not_fake_personalized_value():
    scenarios = {scenario["id"]: scenario for scenario in _load()["scenarios"]}
    incomplete = scenarios["PROFILE_INCOMPLETE"]
    assert incomplete["expected_outcome"] == "EDIT_PROFILE_REQUIRED"
    assert incomplete["next_action"] == "EDIT_PROFILE"
    assert "personalized_value_received" in incomplete["forbidden_claims"]
