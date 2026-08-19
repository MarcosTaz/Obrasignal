import sqlite3


def test_workflow_api_helpers_are_account_scoped():
    from opportunity_workflow import get_workflow, set_workflow

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    a = set_workflow(conn, "empresa-a", "TED", "X-1", "PREPARING", "Montar orçamento")
    b = get_workflow(conn, "empresa-b", "TED", "X-1")

    assert a["status"] == "PREPARING"
    assert a["note"] == "Montar orçamento"
    assert b["status"] == "NEW"
    assert b["note"] is None
    conn.close()
