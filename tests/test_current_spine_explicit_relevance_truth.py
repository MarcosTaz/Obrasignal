"""Current-spine failing-before for explicit company relevance authority."""
import sqlite3

from account_registry import ensure_account
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
        "external_id": "CURRENT-REL-1",
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


def test_review_without_company_specific_evidence_cannot_emit_relevant_shortlist():
    """REVIEW from broad recall is not proof that the opportunity is relevant."""
    conn = _conn()
    result = evaluate_and_record(conn, _row(), _profile(), account_id="tenant-a")
    assert result["decision"] == "REVIEW"
    names = {
        row[0]
        for row in conn.execute(
            "SELECT event_name FROM evaluation_events WHERE account_id='tenant-a'"
        ).fetchall()
    }
    assert "market_data_available" in names
    assert "first_shortlist_generated" not in names, (
        "REVIEW_COERCED_TO_RELEVANCE: broad REVIEW emitted first relevant shortlist without company-specific evidence"
    )


def test_decision_exposes_explicit_versioned_relevance_separate_from_action_label():
    """Consumers need relevance evidence, not inference from QUALIFIED/REVIEW."""
    result = evaluate_row(_row(), _profile())
    relevance = result.get("relevance")
    assert isinstance(relevance, dict), (
        "EXPLICIT_RELEVANCE_AUTHORITY_MISSING: current decision result has no separate relevance contract"
    )
    assert relevance.get("state") == "UNKNOWN"
    assert relevance.get("rule_version")
    assert result.get("relevant_shortlist_eligible") is False


def test_explicit_service_evidence_can_prove_relevance_without_redefining_decision():
    result = evaluate_row(_row(), _profile(services=["estrutura metálica"]))
    relevance = result.get("relevance")
    assert isinstance(relevance, dict)
    assert relevance.get("state") == "RELEVANT"
    assert result.get("relevant_shortlist_eligible") is True
