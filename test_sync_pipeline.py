"""Regression coverage for ingestion -> commercial-v2 decision -> events."""
import sqlite3
from datetime import datetime, timezone

from decision_log import ensure_decision_table, evaluate_and_record if False else None


def _profile():
    return {
        "activity": "estruturas metálicas, pavilhões e serralharia industrial",
        "countries": ["PRT", "ESP", "FRA"],
        "keywords": ["estruturas metálicas", "pavilhões", "serralharia industrial"],
        "exclude_keywords": ["arquitetura", "fiscalização"],
        "cpv_prefixes": ["4522"],
        "min_value": 100000,
        "max_value": 2000000,
        "economic_min_score": 60,
    }


def test_pipeline_scores_and_records_canonical_decision():
    from opportunity_match_pipeline import evaluate_and_record
    from decision_log import latest_decision

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    row = {
        "source": "TED", "external_id": "2026/S-123456",
        "title": "Construção de pavilhão industrial em estruturas metálicas",
        "description": "Fabrico e montagem de estrutura metálica",
        "buyer": "Município", "country": "ESP", "cpv": "45223200",
        "value": "850000", "value_numeric": 850000,
        "deadline": "2099-12-31", "first_seen": datetime.now(timezone.utc).isoformat(),
    }
    evaluation = evaluate_and_record(conn, row, _profile(), account_id="default")
    stored = latest_decision(conn, "TED", "2026/S-123456", account_id="default")
    assert evaluation["decision"] in {"QUALIFIED", "REVIEW", "REJECT"}
    assert stored["rule_version"] == "commercial-v2+lot-v1+capability-v1+economic-fit-v2"
    assert stored["features"]["profile_score"] == evaluation["profile_score"]
    conn.close()
