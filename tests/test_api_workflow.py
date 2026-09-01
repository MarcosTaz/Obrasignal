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


def test_workflow_steady_state_reads_do_not_run_schema_writes():
    from opportunity_workflow import ensure_workflow_table, get_workflow, workflow_counts

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_workflow_table(conn)
    statements = []
    conn.set_trace_callback(statements.append)

    assert get_workflow(conn, "empresa-a", "TED", "X-2")["status"] == "NEW"
    counts = workflow_counts(conn, "empresa-a")
    assert counts["NEW"] == 0

    normalized = [statement.strip().upper() for statement in statements]
    assert not any(statement.startswith("CREATE ") for statement in normalized)
    assert not any(statement == "COMMIT" for statement in normalized)
    conn.close()
