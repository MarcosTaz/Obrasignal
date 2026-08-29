import sqlite3
from pathlib import Path


def test_workflow_won_is_customer_reported_not_verified():
    from opportunity_workflow import set_workflow

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        row = set_workflow(conn, "company-a", "TED", "T-1", "WON", "Buyer said awarded")
        assert row["status"] == "WON"
        assert row["outcome_verification"] == "CUSTOMER_REPORTED_UNVERIFIED"
        assert row["verified_outcome"] is False
    finally:
        conn.close()


def test_workflow_lost_is_customer_reported_not_verified():
    from opportunity_workflow import set_workflow

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        row = set_workflow(conn, "company-a", "TED", "T-2", "LOST")
        assert row["status"] == "LOST"
        assert row["outcome_verification"] == "CUSTOMER_REPORTED_UNVERIFIED"
        assert row["verified_outcome"] is False
    finally:
        conn.close()


def test_non_terminal_workflow_is_not_an_outcome():
    from opportunity_workflow import set_workflow

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        row = set_workflow(conn, "company-a", "TED", "T-3", "SUBMITTED")
        assert row["outcome_verification"] == "NOT_AN_OUTCOME"
        assert row["verified_outcome"] is False
    finally:
        conn.close()


def test_mobile_funnel_does_not_present_reported_wins_as_verified_outcomes():
    source = Path("mobile/components/WorkflowFunnel.js").read_text(encoding="utf-8")
    assert "Ganhos reportados" in source
    assert "não verificado" in source.lower()
    assert ">Ganhos: {counts.WON || 0}<" not in source


def test_mobile_detail_qualifies_terminal_workflow_before_it_can_be_read_as_verified_outcome():
    app = Path("mobile/App.js").read_text(encoding="utf-8")
    explanation = Path("mobile/components/OpportunityExplanation.js").read_text(encoding="utf-8")

    # App.js still lets the user record terminal workflow states, but the labels
    # themselves now preserve that these are customer-reported rather than verified.
    assert "['WON','Ganho reportado']" in app
    assert "['LOST','Perdido reportado']" in app
    assert "['WON','Ganho']" not in app
    assert "['LOST','Perdido']" not in app
    assert "<OpportunityExplanation item={current}/>" in app
    assert "ESTADO REPORTADO · NÃO VERIFICADO" in explanation
    assert "Não prova adjudicação, resultado económico, pagamento" in explanation
    assert "workflowStatus === 'WON' || workflowStatus === 'LOST'" in explanation
