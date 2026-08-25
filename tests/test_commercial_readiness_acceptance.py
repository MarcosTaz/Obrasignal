import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "acceptance" / "commercial_readiness.json"


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_minimum_sellable_spine_is_bounded_and_customer_facing():
    data = _contract()
    assert data["product_status"] == "NOT_YET_SELF_SERVICE_SELLABLE"
    assert data["minimum_sellable_spine"] == [
        "SIGNUP",
        "AUTH",
        "PROFILE",
        "FIRST_RELEVANT_SHORTLIST",
        "OPPORTUNITY_DETAIL",
        "OFFICIAL_SOURCE",
        "WORKFLOW_SAVE",
        "RETURNING_USER",
        "EVALUATION",
        "PRO_ENTITLEMENT",
    ]
    assert "Q090" not in data["minimum_sellable_spine"]
    assert "MOBILIZE" not in data["minimum_sellable_spine"]
    assert "BANGS" not in data["minimum_sellable_spine"]


def test_evaluation_cannot_start_at_signup_or_require_card():
    truth = _contract()["commercial_truth"]
    assert truth["evaluation_days"] == 21
    assert truth["evaluation_starts_at_signup"] is False
    assert truth["credit_card_before_evaluation"] is False
    assert truth["evaluation_activation_requires"] == [
        "profile_ready",
        "market_data_available",
        "first_relevant_shortlist_generated",
    ]


def test_paid_contract_matches_existing_revenuecat_surface_without_inventing_web_checkout():
    truth = _contract()["commercial_truth"]
    assert truth["paid_entitlement"] == "pro"
    assert truth["paid_product"] == "obrasignal_pro_monthly"
    assert truth["store_price_must_be_localized"] is True
    assert truth["web_checkout_supported"] is False


def test_sellability_stays_red_until_external_blockers_are_proven():
    data = _contract()
    blockers = {item["id"]: item for item in data["blocking_acceptance"]}
    assert set(blockers) == {"SELL-001", "SELL-002", "SELL-003", "SELL-004", "SELL-005"}
    assert blockers["SELL-001"]["owner"] == "PRODUCTION_AUTH"
    assert blockers["SELL-002"]["owner"] == "BILLING"
    assert "#83" in blockers["SELL-002"]["required_proof"]
    assert blockers["SELL-004"]["owner"] == "ACCOUNT_PRIVACY"
    assert all(item["status"] != "PASS" for item in blockers.values())


def test_forbidden_commercial_claims_cover_core_false_ready_risks():
    claims = set(_contract()["forbidden_commercial_claims"])
    assert {
        "production_ready_without_current_production_acceptance",
        "complete_market_coverage_without_explicit_coverage_contract",
        "all_portuguese_tenders_without_proof",
        "billing_secure_while_known_authority_repair_is_unmerged",
        "branch_only_capability_is_customer_available",
        "missing_evidence_means_negative_evidence",
    } <= claims
