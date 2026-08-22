from company_profile import derive_profile


def test_metalomecanica_activity_derives_terms_and_cpv():
    profile = derive_profile("Fazemos estruturas metálicas, pavilhões e serralharia industrial")
    assert "estrutura metálica" in profile["keywords"]
    assert "serralharia" in profile["keywords"]
    assert "4522" in profile["cpv_prefixes"]


def test_custom_values_are_preserved():
    profile = derive_profile("construção", {"countries": ["PRT", "ESP"], "min_value": 100000})
    assert profile["countries"] == ["PRT", "ESP"]
    assert profile["min_value"] == 100000
    assert "45" in profile["cpv_prefixes"]


def test_natural_contract_interests_derive_matching_criteria():
    profile = derive_profile(
        "serviços técnicos",
        {"contract_interests": ["Instalação elétrica em escolas", "Climatização de edifícios públicos"], "cpv_prefixes": []},
    )
    assert profile["contract_interests"] == ["Instalação elétrica em escolas", "Climatização de edifícios públicos"]
    assert "4531" in profile["cpv_prefixes"]
    assert "4533" in profile["cpv_prefixes"]
    assert "instalação elétrica" in profile["keywords"]


def test_existing_profile_without_new_onboarding_fields_remains_compatible():
    profile = derive_profile("construção", {"keywords": ["obra municipal"], "countries": ["PRT"]})
    assert profile["contract_interests"] == []
    assert profile["coverage_mode"] == "portugal"
    assert "obra municipal" in profile["keywords"]
