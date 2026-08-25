from company_profile import derive_profile
from opportunity_match_pipeline import evaluate_row


ROWS = {
    "metal": {"title": "Fabrico e montagem de estruturas metálicas", "description": "Serralharia e aço", "cpv": "45223100"},
    "building": {"title": "Reabilitação de edifício municipal", "description": "Empreitada de construção", "cpv": "45453100"},
    "electric": {"title": "Instalações elétricas em escola", "description": "Quadros e iluminação", "cpv": "45310000"},
}


def _row(kind):
    return {**ROWS[kind], "country": "PRT", "value_numeric": 200000, "deadline": "2099-01-01"}


def _profile(activity):
    return derive_profile(activity, {"activity": activity, "countries": ["PRT"], "cpv_prefixes": [], "keywords": []})


def test_distinct_trade_profiles_change_ranking_without_high_false_positives():
    metal = {kind: evaluate_row(_row(kind), _profile("serralharia e estruturas metálicas")) for kind in ROWS}
    electric = {kind: evaluate_row(_row(kind), _profile("instalações elétricas")) for kind in ROWS}

    assert metal["metal"]["profile_score"] > metal["building"]["profile_score"]
    assert metal["metal"]["profile_score"] > metal["electric"]["profile_score"]
    assert electric["electric"]["profile_score"] > electric["metal"]["profile_score"]
    assert electric["metal"]["profile_score"] <= 35
    assert electric["metal"]["decision"] == "REJECT"
