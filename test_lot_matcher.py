from lot_matcher import match_lot, match_notice_lots


def profile():
    return {
        "countries": {"PRT"},
        "nuts": {"PT16"},
        "cities": {"LEIRIA"},
        "postal_prefixes": {"24"},
    }


def lot(lot_id, location):
    return {
        "lot_id": lot_id,
        "title": "Construção de estrutura metálica",
        "description": "empreitada de montagem",
        "cpv": "45223100-7",
        "deadline": "2099-12-31",
        "value_numeric": 150000,
        "procedure_type": "open procedure",
        "locations": [location],
    }


def test_lot_city_match_is_preserved_in_combined_result():
    result = match_lot(lot("LOT-1", {"country": "PRT", "city": "Leiria"}), profile())
    assert result["geography"]["score"] == 5
    assert result["geography"]["reason"] == "cidade prioritária"
    assert result["score"] >= 70


def test_multiple_locations_keep_best_match():
    item = lot("LOT-2", {"country": "ESP", "city": "Madrid"})
    item["locations"] = [
        {"country": "ESP", "city": "Madrid"},
        {"country": "PRT", "city": "Leiria"},
    ]
    result = match_lot(item, profile())
    assert result["geography"]["score"] == 5
    assert len(result["all_geography_matches"]) == 2


def test_broad_location_is_not_unknown():
    result = match_lot(lot("LOT-3", {"broad": "anyw-eea"}), profile())
    assert result["geography"]["score"] == 2
    assert result["geography"]["confidence"] == 50


def test_notice_ranks_best_lot_and_runner_up():
    result = match_notice_lots([
        lot("LOT-A", {"country": "ESP", "city": "Madrid"}),
        lot("LOT-B", {"country": "PRT", "city": "Leiria"}),
    ], profile())
    assert result["best_lot"]["lot_id"] == "LOT-B"
    assert result["second_best_lot"]["lot_id"] == "LOT-A"


def test_lot_match_uses_company_radius_when_coordinates_are_available():
    company = {
        "countries": {"PRT"},
        "geographic_radius_km": 20,
        "profile_coordinates": [{"latitude": 39.7480, "longitude": -8.8070}],
    }
    result = match_lot(
        lot("LOT-RADIUS", {"country": "PRT", "latitude": 39.7444, "longitude": -8.8073}),
        company,
    )
    assert result["geography"]["score"] == 5
    assert "raio geográfico" in result["geography"]["reason"]


def test_lot_match_penalizes_location_outside_company_radius():
    company = {
        "countries": {"PRT"},
        "geographic_radius_km": 20,
        "profile_coordinates": [{"latitude": 39.7480, "longitude": -8.8070}],
    }
    result = match_lot(
        lot("LOT-FAR", {"country": "PRT", "latitude": 38.7223, "longitude": -9.1393}),
        company,
    )
    assert result["geography"]["score"] == 1
    assert "fora do raio geográfico" in result["geography"]["reason"]
