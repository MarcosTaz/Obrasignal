from geo_profile import geographic_fit


def test_priority_nuts_gets_full_geographic_score():
    result = geographic_fit(
        {"country_code": "PRT", "nuts_codes": ["PT16"], "city": "Leiria"},
        {"countries": {"PRT"}, "nuts": {"PT16"}, "cities": {"LEIRIA"}, "postal_prefixes": set()},
    )
    assert result["score"] == 5
    assert result["confidence"] == 100


def test_same_country_without_priority_is_partial():
    result = geographic_fit(
        {"country_code": "PRT", "city": "Porto"},
        {"countries": {"PRT"}, "nuts": {"PT16"}, "cities": {"LEIRIA"}, "postal_prefixes": set()},
    )
    assert result["score"] == 3


def test_outside_country_is_zero():
    result = geographic_fit(
        {"country_code": "ESP"},
        {"countries": {"PRT"}, "nuts": set(), "cities": set(), "postal_prefixes": set()},
    )
    assert result["score"] == 0


def test_unknown_location_is_low_confidence():
    result = geographic_fit({}, {"countries": {"PRT"}, "nuts": set(), "cities": set(), "postal_prefixes": set()})
    assert result["confidence"] < 50
