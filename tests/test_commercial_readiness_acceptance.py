import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "acceptance" / "commercial_readiness.json"


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_minimum_sellable_spine_is_bounded_and_customer_facing():
    data = _contract()
    assert data["product_status"] == "NOT_YET_SELF_SERVICE_SELLABLE"
    assert data["minimum_sellable_spine"] == ["SIGNUP","AUTH","PROFILE","FIRST_RELEVANT_SHORTLIST","OPPORTUNITY_DETAIL","OFFICIAL_SOURCE","WORKFLOW_SAVE","RETURNING_USER","EVALUATION","PRO_ENTITLEMENT"]
    assert not {"Q090", "MOBILIZE", "BANGS"} & set(data["minimum_sellable_spine"])


def test_current_main_has_exact_production_auth_spine_proof():
    data = _contract()
    proven = {item["id"]: item for item in data["proven_acceptance"]}
    assert {"SELL-001", "SELL-004-CONTRACT", "SELL-005-CONTRACT"} <= set(proven)
    assert proven["SELL-001"]["main_sha"] == data["baseline_main_sha"]
    assert proven["SELL-001"]["status"] == "PASS_EXACT_MAIN"
    assert proven["SELL-001"]["authenticated_e2e_run"] == 32867427570
    assert {"authenticated_api_identity", "profile_persistence_round_trip", "opportunity_account_scoping", "detail_and_workflow_round_trip_when_data_exists"} <= set(proven["SELL-001"]["proof"])


def test_source_coverage_contract_exists_without_claiming_customer_surface_is_done():
    data = _contract()
    proven = {item["id"]: item for item in data["proven_acceptance"]}
    coverage = proven["SELL-005-CONTRACT"]
    assert coverage["status"] == "ACCEPTANCE_CONTRACT_IMPLEMENTED_PENDING_EXACT_HEAD_GATE"
    assert {"registered_not_active", "ready_not_active", "source_presence_not_national_completeness", "capability_scope_not_full_market_claim"} <= set(coverage["proof"])
    blockers = {item["id"]: item for item in data["blocking_acceptance"]}
    assert blockers["SELL-005"]["status"] == "IMPLEMENTATION_HANDOFF_AFTER_ACCEPTANCE_CONTRACT"


def test_account_lifecycle_contract_is_owned_but_implementation_stays_external():
    data = _contract()
    proven = {item["id"]: item for item in data["proven_acceptance"]}
    account = proven["SELL-004-CONTRACT"]
    assert account["contract"] == "acceptance/account_lifecycle.json"
    assert account["status"] == "ACCEPTANCE_CONTRACT_IMPLEMENTED_PENDING_EXACT_HEAD_GATE"
    blockers = {item["id"]: item for item in data["blocking_acceptance"]}
    assert blockers["SELL-004"]["owner"] == "ACCOUNT_PRIVACY_AUTH"
    assert blockers["SELL-004"]["status"] == "IMPLEMENTATION_HANDOFF_AFTER_ACCEPTANCE_CONTRACT"


def test_evaluation_cannot_start_at_signup_or_require_card():
    truth = _contract()["commercial_truth"]
    assert truth["evaluation_days"] == 21
    assert truth["evaluation_starts_at_signup"] is False
    assert truth["credit_card_before_evaluation"] is False
    assert truth["evaluation_activation_requires"] == ["profile_ready","market_data_available","first_relevant_shortlist_generated"]


def test_paid_contract_matches_existing_revenuecat_surface_without_inventing_web_checkout():
    truth = _contract()["commercial_truth"]
    assert truth["paid_entitlement"] == "pro"
    assert truth["paid_product"] == "obrasignal_pro_monthly"
    assert truth["store_price_must_be_localized"] is True
    assert truth["web_checkout_supported"] is False


def test_remaining_sellability_blockers_are_exact_and_non_green():
    blockers = {item["id"]: item for item in _contract()["blocking_acceptance"]}
    assert set(blockers) == {"SELL-002", "SELL-003", "SELL-004", "SELL-005"}
    billing = blockers["SELL-002"]
    assert billing["owner"] == "BILLING"
    assert billing["current_candidate_pr"] == 83
    assert billing["current_candidate_head"] == "3c00cff49211dad2cd54650aeb838dc5f5301f3f"
    assert billing["current_candidate_base"] == _contract()["baseline_main_sha"]
    assert billing["current_gates"] == {"billing_security": "FAIL", "quality": "FAIL"}
    assert blockers["SELL-004"]["owner"] == "ACCOUNT_PRIVACY_AUTH"
    assert all(not item["status"].startswith("PASS") for item in blockers.values())


def test_forbidden_commercial_claims_cover_core_false_ready_risks():
    claims = set(_contract()["forbidden_commercial_claims"])
    assert {"production_ready_without_current_production_acceptance","complete_market_coverage_without_explicit_coverage_contract","all_portuguese_tenders_without_proof","billing_secure_while_known_authority_repair_is_unmerged","branch_only_capability_is_customer_available","missing_evidence_means_negative_evidence"} <= claims
