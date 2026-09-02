from capability_profile import build_capability_profile, capability_matches_text


def test_saved_contract_interest_matches_portuguese_inflection():
    profile = build_capability_profile({
        "activity": "instalações elétricas",
        "contract_interests": ["instalações elétricas em escolas"],
    })
    evidence = capability_matches_text(
        profile,
        "Empreitada para instalação elétrica e trabalhos associados em escolas municipais",
    )
    assert evidence["matched"] is True
    assert evidence["matched_services"] == ["instalações elétricas em escolas"]


def test_primary_activity_is_valid_profile_evidence():
    profile = build_capability_profile({"activity": "construção"})
    evidence = capability_matches_text(
        profile,
        "Construção de edifício para serviços municipais",
    )
    assert evidence["matched"] is True
    assert evidence["matched_activity"] == "construção"


def test_unrelated_profile_does_not_match_generic_procurement_text():
    profile = build_capability_profile({
        "activity": "instalações elétricas",
        "contract_interests": ["quadros elétricos"],
    })
    evidence = capability_matches_text(
        profile,
        "Aquisição de mobiliário administrativo e cadeiras de escritório",
    )
    assert evidence["matched"] is False
