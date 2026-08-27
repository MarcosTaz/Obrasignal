"""Failing-before probe for workflow terminal-state resurrection on current trust spine."""
import sqlite3

from opportunity_workflow import ensure_workflow_table, get_workflow, set_workflow


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_workflow_table(conn)
    return conn


def test_won_cannot_resurrect_to_reviewing_without_explicit_domain_reopen_contract():
    conn = _conn()
    set_workflow(conn, "tenant-a", "TED", "opp-1", "WON", "terminal")
    try:
        set_workflow(conn, "tenant-a", "TED", "opp-1", "REVIEWING", "resurrect")
    except ValueError:
        pass
    else:
        raise AssertionError("terminal WON resurrected to REVIEWING")
    assert get_workflow(conn, "tenant-a", "TED", "opp-1")["status"] == "WON"


def test_lost_cannot_resurrect_to_new_without_explicit_domain_reopen_contract():
    conn = _conn()
    set_workflow(conn, "tenant-a", "TED", "opp-2", "LOST", "terminal")
    try:
        set_workflow(conn, "tenant-a", "TED", "opp-2", "NEW", "resurrect")
    except ValueError:
        pass
    else:
        raise AssertionError("terminal LOST resurrected to NEW")
    assert get_workflow(conn, "tenant-a", "TED", "opp-2")["status"] == "LOST"
