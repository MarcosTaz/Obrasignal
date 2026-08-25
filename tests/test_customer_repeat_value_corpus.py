import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "customer_repeat_value_corpus.json"
FACTORY_TITLE = "Customer Journey, First Value & Outcome Integrity"
CANONICAL_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"
EXPECTED_SCENARIOS = {
    "NEW_RELEVANT_OPPORTUNITY",
    "CURRENT_OPPORTUNITY_MATERIAL_CHANGE",
    "WORKFLOW_CONTINUATION",
    "SAVED_OPPORTUNITY_CHANGE",
    "SOURCE_COVERAGE_RECOVERED",
    "NOTIFICATION_DELIVERED_ONLY",
    "RETURN_NO_MATERIAL_CHANGE",
    "STALE_CACHE_RETURN",
    "BILLING_STATE_CHANGED_ONLY",
}


def _load():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _scenarios():
    return {scenario["id"]: scenario for scenario in _load()["scenarios"]}


def test_repeat_value_corpus_is_exact_factory_and_exact_canonical_head():
    corpus = _load()
    assert corpus["factory_title"] == FACTORY_TITLE
    assert corpus["canonical_main_sha"] == CANONICAL_MAIN
    assert {scenario["id"] for scenario in corpus["scenarios"]} == EXPECTED_SCENARIOS


def test_notification_delivery_return_visit_cache_and_billing_are_not_repeat_value_alone():
    contract = _load()["repeat_value_candidate_contract"]
    insufficient = set(contract["not_sufficient_alone"])
    assert {
        "app_opened",
        "web_returned",
        "radar_refreshed",
        "cache_hydrated",
        "notification_sent",
        "alert_delivered",
        "notification_opened",
        "subscription_active",
        "workflow_state_present",
        "saved_record_present",
    }.issubset(insufficient)

    scenarios = _scenarios()
    assert scenarios["NOTIFICATION_DELIVERED_ONLY"]["expected_outcome"] == "NO_NEW_VALUE"
    assert scenarios["RETURN_NO_MATERIAL_CHANGE"]["expected_outcome"] == "CONTINUITY_ONLY"
    assert scenarios["STALE_CACHE_RETURN"]["expected_outcome"] == "CURRENTNESS_UNCONFIRMED"
    assert scenarios["BILLING_STATE_CHANGED_ONLY"]["expected_outcome"] == "NO_NEW_VALUE"


def test_new_relevant_opportunity_requires_current_owner_resolved_truth():
    scenario = _scenarios()["NEW_RELEVANT_OPPORTUNITY"]
    assert scenario["expected_outcome"] == "REPEAT_VALUE_CANDIDATE"
    assert scenario["currentness"] == "CURRENT_SUFFICIENT_FOR_CLAIM"
    assert "Decision Intelligence" in scenario["owner_dependencies"]
    assert "duplicate_record_is_new_value" in scenario["forbidden_claims"]


def test_material_change_can_be_repeat_value_but_timestamp_churn_cannot():
    scenario = _scenarios()["CURRENT_OPPORTUNITY_MATERIAL_CHANGE"]
    assert scenario["expected_outcome"] == "REPEAT_VALUE_CANDIDATE"
    assert scenario["currentness"] == "CURRENT_AUTHORITY_RESOLVED"
    assert "any_timestamp_change_is_value" in scenario["forbidden_claims"]


def test_saved_change_stays_prebuild_until_saved_contract_is_current():
    scenario = _scenarios()["SAVED_OPPORTUNITY_CHANGE"]
    assert scenario["expected_outcome"] == "PREBUILD_DEPENDENCY"
    assert "#150 reanchor" in scenario["owner_dependencies"][0]
    assert "stale_watchlist_candidate_is_canonical" in scenario["forbidden_claims"]


def test_workflow_continuation_does_not_invent_state_machine_semantics():
    scenario = _scenarios()["WORKFLOW_CONTINUATION"]
    assert scenario["expected_outcome"] == "OWNER_SEMANTICS_REQUIRED"
    assert "State Machine/Workflow" in scenario["owner_dependencies"]
    assert "system_state_proves_real_world_progress" in scenario["forbidden_claims"]


def test_source_recovery_requires_useful_truth_not_health_flip_alone():
    scenario = _scenarios()["SOURCE_COVERAGE_RECOVERED"]
    assert scenario["expected_outcome"] == "REPEAT_VALUE_CANDIDATE"
    assert "health_status_change_alone_is_customer_value" in scenario["forbidden_claims"]
    assert "noncanonical_source_health_is_canonical" in scenario["forbidden_claims"]
