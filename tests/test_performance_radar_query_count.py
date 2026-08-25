import json
import sqlite3

from decision_log import ensure_decision_table
from radar_decision_feed import enrich_rows


def _decision_row(account_id, index, decision, reason=None):
    return (
        account_id,
        "BENCH",
        f"bench-{index:03d}",
        decision,
        reason or f"{account_id}-{decision}",
        80 if account_id == "tenant-a" else 10,
        json.dumps({"profile_score": 80 if account_id == "tenant-a" else 10}),
        "perf-test-v1",
        f"2026-08-25T00:00:{index % 60:02d}+00:00",
    )


def _seed_decisions(conn, account_id, count, decision):
    conn.executemany(
        """INSERT INTO opportunity_decisions
           (account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [_decision_row(account_id, index, decision) for index in range(count)],
    )
    conn.commit()


def test_radar_decision_enrichment_is_constant_query_count_and_tenant_safe():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    # Tenant B is inserted later than tenant A so a broken global-latest batch
    # would deterministically leak the wrong tenant's decision.
    _seed_decisions(conn, "tenant-a", 99, "QUALIFIED")
    _seed_decisions(conn, "tenant-b", 100, "REJECT")
    conn.execute(
        """INSERT INTO opportunity_decisions
           (account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        _decision_row("tenant-a", 50, "REVIEW", reason="tenant-a-latest"),
    )
    conn.commit()

    radar_rows = [
        {"source": "BENCH", "external_id": f"bench-{index:03d}", "title": f"Tender {index}"}
        for index in range(100)
    ]
    traced = []
    conn.set_trace_callback(traced.append)
    try:
        enriched = enrich_rows(conn, radar_rows, account_id="tenant-a")
    finally:
        conn.set_trace_callback(None)
        conn.close()

    assert len(enriched) == 100
    assert enriched[0]["decision_summary"]["status"] == "QUALIFIED"
    assert enriched[50]["decision_summary"]["status"] == "REVIEW"
    assert enriched[50]["decision_summary"]["reason"] == "tenant-a-latest"
    assert enriched[99]["decision_summary"]["status"] == "SEM DECISÃO"
    assert all(
        item["decision_summary"]["reason"] != "tenant-b-REJECT"
        for item in enriched
    )

    decision_sql = [statement for statement in traced if "opportunity_decisions" in statement.lower()]
    assert len(decision_sql) == 3, f"decision_query_count={len(decision_sql)}"
