from company_profile import derive_profile


def test_metalomecanica_activity_derives_terms_and_cpv():
    profile = derive_profile("Fazemos estruturas metálicas, pavilhões e serralharia industrial")
    assert "estrutura metálica" in profile["keywords"]
    assert "serralharia" in profile["keywords"]
    assert "45" in profile["cpv_prefixes"]


def test_custom_values_are_preserved():
    profile = derive_profile("construção", {"countries": ["PRT", "ESP"], "min_value": 100000})
    assert profile["countries"] == ["PRT", "ESP"]
    assert profile["min_value"] == 100000
    assert "45" in profile["cpv_prefixes"]
