import sqlite3

from account_registry import ensure_account
from decision_relevance import (
    NOT_RELEVANT,
    RELEVANCE_RULE_VERSION,
    RELEVANT,
    UNKNOWN,
    relevance_state_from_features,
    relevant_shortlist_eligible_from_features,
)
from opportunity_match_pipeline import evaluate_and_record, evaluate_row


def _profile(**overrides):
    profile = {
        "countries": {"PRT"},
        "nuts": set(),
        "cities": {"LEIRIA"},
        "postal_prefixes": {"24"},
        "min_value": 100000,
        "max_value": 300000,
    }
    profile.update(overrides)
    return profile


def _row(**overrides):
    row = {
        "source": "TED",
        "external_id": "REL-1",
        "title": "Construção de estrutura metálica",
        "description": "empreitada de montagem",
        "country": "PRT",
        "cpv": "45223100-7",
        "value_numeric": 150000,
        "deadline": "2099-12-31",
        "locations": [{"country": "PRT", "city": "Leiria"}],
    }
    row.update(overrides)
    return row


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_account(conn, "tenant-a")
    return conn


def test_geography_and_economics_review_remains_relevance_unknown_and_not_eligible():
    result = evaluate_row(_row(), _profile())

    assert result["decision"] == "REVIEW"
    assert result["relevance"]["state"] == UNKNOWN
    assert result["relevance"]["evidence"] == []
    assert result["relevance"]["rule_version"] == RELEVANCE_RULE_VERSION
    assert result["relevant_shortlist_eligible"] is False


def test_explicit_service_evidence_proves_relevance_without_redefining_action_label():
    result = evaluate_row(
        _row(),
        _profile(services=["estrutura metálica"]),
    )

    assert result["relevance"]["state"] == RELEVANT
    assert {item["kind"] for item in result["relevance"]["evidence"]} == {"service"}
    assert result["relevant_shortlist_eligible"] is True


def test_specific_cpv_prefix_is_company_relevance_evidence():
    result = evaluate_row(
        _row(title="Obra civil", description="empreitada"),
        _profile(cpv_prefixes=["4522"]),
    )

    assert result["relevance"]["state"] == RELEVANT
    assert {item["kind"] for item in result["relevance"]["evidence"]} == {"cpv_prefix"}
    assert result["relevant_shortlist_eligible"] is True


def test_explicit_cpv_conflict_is_not_relevant_and_not_eligible():
    result = evaluate_row(
        _row(cpv="71200000", title="Serviços de arquitetura", description="consultoria"),
        _profile(cpv_prefixes=["4522"]),
    )

    assert result["relevance"]["state"] == NOT_RELEVANT
    assert result["relevant_shortlist_eligible"] is False
    assert "CPV fora das famílias aceites pela empresa" in result["hard_capability_blockers"]


def test_relevant_but_hard_blocked_does_not_become_shortlist_eligible():
    result = evaluate_row(
        _row(value_numeric=150000),
        _profile(services=["estrutura metálica"], max_value=100000),
    )

    assert result["relevance"]["state"] == RELEVANT
    assert result["relevant_shortlist_eligible"] is False
    assert "valor acima do máximo da empresa" in result["hard_capability_blockers"]


def test_historical_or_stale_relevance_features_fail_closed_to_unknown():
    assert relevance_state_from_features({"decision": "REVIEW"}) == UNKNOWN
    assert relevant_shortlist_eligible_from_features({"decision": "REVIEW"}) is False

    stale = {
        "relevance": {
            "state": RELEVANT,
            "evidence": [{"kind": "service", "value": "estrutura metálica"}],
            "rule_version": "relevance-v0",
        },
        "relevant_shortlist_eligible": True,
    }
    assert relevance_state_from_features(stale) == UNKNOWN
    assert relevant_shortlist_eligible_from_features(stale) is False


def test_review_unknown_does_not_emit_first_relevant_shortlist_event():
    conn = _conn()
    result = evaluate_and_record(conn, _row(), _profile(), account_id="tenant-a")

    assert result["decision"] == "REVIEW"
    assert result["relevance"]["state"] == UNKNOWN
    names = {
        row[0]
        for row in conn.execute(
            "SELECT event_name FROM evaluation_events WHERE account_id='tenant-a'"
        ).fetchall()
    }
    assert "market_data_available" in names
    assert "first_shortlist_generated" not in names


def test_explicit_relevance_eligibility_emits_versioned_shortlist_event():
    conn = _conn()
    result = evaluate_and_record(
        conn,
        _row(),
        _profile(services=["estrutura metálica"]),
        account_id="tenant-a",
    )

    assert result["relevant_shortlist_eligible"] is True
    row = conn.execute(
        "SELECT metadata_json FROM evaluation_events WHERE account_id=? AND event_name='first_shortlist_generated'",
        ("tenant-a",),
    ).fetchone()
    assert row is not None
    assert '"relevance_state":"RELEVANT"' in row[0]
    assert f'"relevance_rule_version":"{RELEVANCE_RULE_VERSION}"' in row[0]
