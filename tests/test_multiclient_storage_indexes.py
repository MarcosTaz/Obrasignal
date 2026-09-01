import sqlite3

from decision_log import DECISION_ACCOUNT_INDEX, ensure_decision_table
from notification_events import ensure_event_table
from push_runtime import ensure_push_schema


def _indexes(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA index_list('{table}')").fetchall()}


def test_high_volume_customer_tables_have_tenant_first_indexes():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    ensure_event_table(conn)
    ensure_push_schema(conn)

    assert DECISION_ACCOUNT_INDEX in _indexes(conn, "opportunity_decisions")
    assert "idx_opportunity_events_account_feed" in _indexes(conn, "opportunity_events")
    assert "idx_opportunity_events_account_delivery" in _indexes(conn, "opportunity_events")
    assert "idx_push_devices_account" in _indexes(conn, "push_devices")
    conn.close()
