from company_profile_validation import validate_company_profile


def test_valid_profile_has_no_errors():
    profile = {
        "countries": ["PRT", "ESP"],
        "regions": ["Leiria"],
        "services": ["fabrico"],
        "capability_tags": ["aço"],
        "cpv_prefixes": ["45", "4411"],
        "min_value": 100000,
        "max_value": 1000000,
        "economic_min_score": 60,
        "min_deadline_days": 15,
        "max_deadline_days": 90,
        "geographic_radius_km": 100,
    }
    assert validate_company_profile(profile) == []


def test_rejects_inverted_value_and_deadline_ranges():
    errors = validate_company_profile({
        "min_value": 1000000,
        "max_value": 100000,
        "min_deadline_days": 90,
        "max_deadline_days": 15,
    })
    assert "min_value: não pode ser superior a max_value." in errors
    assert "min_deadline_days: não pode ser superior a max_deadline_days." in errors


def test_rejects_invalid_numeric_ranges():
    errors = validate_company_profile({
        "economic_min_score": 101,
        "geographic_radius_km": -1,
        "min_value": -100,
    })
    assert "economic_min_score: não pode ser superior a 100." in errors
    assert "geographic_radius_km: não pode ser inferior a 0." in errors
    assert "min_value: não pode ser inferior a 0." in errors


def test_rejects_invalid_country_and_cpv_values():
    errors = validate_company_profile({
        "countries": ["PT", ""],
        "cpv_prefixes": ["X5", "4", "123456789"],
    })
    assert any(error.startswith("countries:") for error in errors)
    assert "cpv_prefixes: prefixo inválido 'X5'." in errors
    assert "cpv_prefixes: prefixo inválido '4'." in errors
    assert "cpv_prefixes: prefixo inválido '123456789'." in errors


def test_rejects_non_list_fields():
    errors = validate_company_profile({
        "regions": "Leiria",
        "services": [""],
    })
    assert "regions: deve ser uma lista." in errors
    assert "services: contém valores vazios ou inválidos." in errors
