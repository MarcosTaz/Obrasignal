from lot_matcher import match_lot, rank_lots


def profile():
    return {
        "countries": ["prt"],
        "nuts3": ["pt16"],
        "cities": ["leiria"],
        "postcodes": ["2400-000"],
    }


def test_lot_city_match_beats_country_only():
    result = match_lot({"lot_id": "LOT-1", "locations": [{"country": "PRT", "city": "Leiria"}]}, profile())
    assert result["geo_score"] == 5
    assert result["geo_status"] == "MATCHED"
    assert result["geo_reason"] == "city"


def test_multiple_locations_keep_best_match():
    result = match_lot({"lot_id": "LOT-2", "locations": [
        {"country": "ESP", "city": "Madrid"},
        {"country": "PRT", "city": "Leiria"},
    ]}, profile())
    assert result["geo_score"] == 5
    assert len(result["location_matches"]) == 2


def test_broad_location_is_not_unknown():
    result = match_lot({"lot_id": "LOT-3", "locations": [{"broad": "anyw-eea"}]}, profile())
    assert result["geo_status"] == "BROAD"
    assert result["geo_score"] == 2


def test_rank_lots_finds_actionable_lot_first():
    lots = [
        {"lot_id": "LOT-A", "locations": [{"country": "ESP", "city": "Madrid"}]},
        {"lot_id": "LOT-B", "locations": [{"country": "PRT", "city": "Leiria"}]},
    ]
    ranked = rank_lots(lots, profile())
    assert ranked[0]["lot_id"] == "LOT-B"
    assert ranked[0]["geo_match"]["geo_score"] == 5
