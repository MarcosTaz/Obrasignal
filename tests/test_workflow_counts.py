import sqlite3


def test_workflow_counts_returns_all_statuses_and_isolates_accounts():
    from opportunity_workflow import STATUSES, set_workflow, workflow_counts

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    set_workflow(conn, "empresa-a", "TED", "X-1", "REVIEWING")
    set_workflow(conn, "empresa-a", "TED", "X-2", "PREPARING")
    set_workflow(conn, "empresa-b", "TED", "X-3", "WON")

    a = workflow_counts(conn, "empresa-a")
    b = workflow_counts(conn, "empresa-b")

    assert set(a) == set(STATUSES)
    assert set(b) == set(STATUSES)
    assert a["REVIEWING"] == 1
    assert a["PREPARING"] == 1
    assert a["WON"] == 0
    assert b["WON"] == 1
    assert b["REVIEWING"] == 0
    conn.close()
