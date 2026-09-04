import json
from pathlib import Path


BASE = Path("factories/industrial-claims/GTM_COHORT_1.json")
EXPANSION = Path("factories/industrial-claims/GTM_COHORT_EXPANSION_6.json")


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _targets():
    return _load(BASE)["targets"] + _load(EXPANSION)["targets"]


def test_combined_gtm_research_contains_ten_unique_named_buyer_targets():
    targets = _targets()
    assert len(targets) == 10
    assert len({item["account_id"] for item in targets}) == 10
    assert len({(item["company"], item["target_person"]) for item in targets}) == 10
    assert all(item["target_person"].strip() for item in targets)
    assert all(item["target_role"].strip() for item in targets)


def test_expansion_does_not_invent_market_proof_or_personal_contact_data():
    payload = _load(EXPANSION)
    assert payload["commercial_truth"] == {
        "outbound_sent": False,
        "buyer_interest_proven": False,
        "customer_leakage_proven": False,
        "recoverable_value_proven": False,
        "paid_customer_proven": False,
        "confidential_documents_requested": False,
        "enrichment_credits_used": False,
    }
    for item in payload["targets"]:
        assert item["email"] is None
        assert item["phone"] is None
        assert item["outbound_authorized"] is False
        assert item["role_sources"]
        assert all(source["url"].startswith("https://") for source in item["role_sources"])


def test_only_mold_tech_target_requires_role_recheck_before_outbound():
    expansion = _load(EXPANSION)["targets"]
    recheck = [item for item in expansion if item["role_recheck_required_before_outbound"]]
    assert len(recheck) == 1
    assert recheck[0]["account_id"] == "mold-tech-portugal-pt"
    assert recheck[0]["role_confidence"] == "MEDIUM_CURRENT_AFFILIATION_OLDER_TITLE"
    assert "ROLE_RECHECK" in recheck[0]["contact_route"]


def test_generic_company_contacts_are_explicitly_not_personal_or_authorized():
    expansion = _load(EXPANSION)["targets"]
    with_company_contact = [item for item in expansion if "public_company_contact_source" in item]
    assert {item["account_id"] for item in with_company_contact} == {"swj-portugal-pt", "mold-tech-portugal-pt"}
    for item in with_company_contact:
        source = item["public_company_contact_source"]
        assert source["generic_email"]
        assert source["generic_phone"]
        assert "not a personal address" in source["note"]
        assert "not authorization to send" in source["note"]
        assert item["outbound_authorized"] is False


def test_public_fit_language_remains_discovery_only_across_all_ten_accounts():
    forbidden = ("has leakage", "is owed", "confirmed claim", "guaranteed recovery", "recoverable amount proven")
    for item in _targets():
        fit = item["public_fit"].lower()
        assert all(term not in fit for term in forbidden)
