import sqlite3

from opportunity_workflow import ensure_workflow_table, get_workflow


def _seed_workflows(conn, account_id, count, status):
    conn.executemany(
        """INSERT INTO opportunity_workflow
           (account_id,source,external_id,status,note,updated_at)
           VALUES (?,?,?,?,?,?)""",
        [
            (
                account_id,
                "BENCH",
                f"bench-{index:03d}",
                status,
                f"{account_id}-{status}",
                f"2026-08-25T00:00:{index % 60:02d}+00:00",
            )
            for index in range(count)
        ],
    )
    conn.commit()


def test_collection_workflow_reads_have_constant_query_count_and_tenant_scope():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_workflow_table(conn)
    _seed_workflows(conn, "tenant-a", 99, "REVIEWING")
    _seed_workflows(conn, "tenant-b", 100, "LOST")

    keys = [("BENCH", f"bench-{index:03d}") for index in range(100)]
    traced = []
    conn.set_trace_callback(traced.append)
    try:
        workflows = {
            key: get_workflow(conn, "tenant-a", key[0], key[1])
            for key in keys
        }
    finally:
        conn.set_trace_callback(None)
        conn.close()

    assert workflows[("BENCH", "bench-000")]["status"] == "REVIEWING"
    assert workflows[("BENCH", "bench-099")]["status"] == "NEW"
    assert workflows[("BENCH", "bench-099")]["account_id"] == "tenant-a"
    assert all(item["status"] != "LOST" for item in workflows.values())

    workflow_sql = [statement for statement in traced if "opportunity_workflow" in statement.lower()]
    assert len(workflow_sql) <= 6, f"workflow_query_count={len(workflow_sql)}"
