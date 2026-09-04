import json
from pathlib import Path


COHORT = Path("factories/industrial-claims/GTM_COHORT_1.json")


def _payload():
    return json.loads(COHORT.read_text(encoding="utf-8"))


def test_cohort_preserves_market_truth_and_has_no_fake_validation():
    payload = _payload()
    assert payload["product"] == "VINDORUM"
    truth = payload["commercial_truth"]
    assert truth == {
        "outbound_sent": False,
        "buyer_interest_proven": False,
        "customer_leakage_proven": False,
        "recoverable_value_proven": False,
        "paid_customer_proven": False,
        "confidential_documents_requested": False,
        "enrichment_credits_used": False,
    }


def test_cohort_contains_only_evidence_grounded_named_roles_and_no_guessed_contact_data():
    targets = _payload()["targets"]
    assert len(targets) == 4
    assert {item["company"] for item in targets} == {
        "TMG Automotive", "Simoldes Plastics", "FEHST Componentes", "HFA, S.A."
    }
    for item in targets:
        assert item["target_person"].strip()
        assert item["target_role"].strip()
        assert item["role_confidence"].startswith("HIGH_")
        assert item["role_sources"]
        assert all(source["url"].startswith("https://") for source in item["role_sources"])
        assert item["email"] is None
        assert item["phone"] is None
        assert item["outbound_authorized"] is False
        assert item["contact_route"] == "PUBLIC_LINKEDIN_OR_COMPANY_CHANNEL_ONLY"


def test_public_fit_is_a_discovery_hypothesis_not_a_claim_allegation():
    forbidden = ("has leakage", "is owed", "recoverable amount", "guaranteed recovery", "confirmed claim")
    for item in _payload()["targets"]:
        text = item["public_fit"].lower()
        assert all(term not in text for term in forbidden)
        assert "outbound_authorized" in item


def test_hfa_contact_source_keeps_same_person_identity_unresolved():
    hfa = next(item for item in _payload()["targets"] if item["account_id"] == "hfa-electronics-pt")
    note = hfa["public_company_contact_source"]["note"]
    assert "Do not assume" in note
    assert "same individual" in note
