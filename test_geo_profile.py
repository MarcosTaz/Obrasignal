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


def test_priority_region_gets_full_geographic_score():
    result = geographic_fit(
        {"country_code": "PRT", "region": "LEIRIA"},
        {"countries": {"PRT"}, "regions": {"LEIRIA"}},
    )
    assert result["score"] == 5
    assert result["confidence"] == 100
    assert result["reason"] == "região prioritária"


def test_radius_accepts_opportunity_inside_company_radius():
    result = geographic_fit(
        {"country_code": "PRT", "latitude": 39.7444, "longitude": -8.8073},
        {
            "countries": {"PRT"},
            "geographic_radius_km": 20,
            "profile_coordinates": [{"latitude": 39.7480, "longitude": -8.8070}],
        },
    )
    assert result["score"] == 5
    assert result["confidence"] == 100
    assert result["distance_km"] < 1


def test_radius_rejects_opportunity_outside_company_radius():
    result = geographic_fit(
        {"country_code": "PRT", "latitude": 38.7223, "longitude": -9.1393},
        {
            "countries": {"PRT"},
            "geographic_radius_km": 20,
            "profile_coordinates": [{"latitude": 39.7480, "longitude": -8.8070}],
        },
    )
    assert result["score"] == 1
    assert result["confidence"] == 100
    assert result["distance_km"] > 100


def test_radius_without_coordinates_does_not_invent_match():
    result = geographic_fit(
        {"country_code": "PRT", "city": "Coimbra"},
        {"countries": {"PRT"}, "geographic_radius_km": 20, "profile_coordinates": []},
    )
    assert result["reason"] == "país compatível"
    assert result["confidence"] == 80
