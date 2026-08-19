import sqlite3

from decision_log import ensure_decision_table, latest_decision
from opportunity_match_pipeline import evaluate_and_record


def test_evaluate_and_record_persists_profile_score_in_features():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    row = {
        "source": "TED",
        "external_id": "FEATURE-1",
        "title": "Construção de estrutura metálica",
        "description": "montagem de estruturas metálicas",
        "country": "PRT",
        "cpv": "45223100-7",
        "value_numeric": 150000,
        "deadline": "2099-12-31",
        "profile_score": 82,
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }
    profile = {
        "countries": ["PRT"],
        "regions": ["Leiria"],
        "cpv_prefixes": ["45"],
        "min_value": 100000,
        "max_value": 300000,
        "economic_min_score": 60,
    }

    evaluation = evaluate_and_record(conn, row, profile)
    stored = latest_decision(conn, "TED", "FEATURE-1")

    assert 0 <= evaluation["profile_score"] <= 100
    assert evaluation["profile_score"] != row["profile_score"]
    assert stored["features"]["profile_score"] == evaluation["profile_score"]
    assert stored["features"]["lot_score"] == evaluation["lot_score"]
    assert "economic_fit" in stored["features"]
    assert "geography" in stored["features"]
