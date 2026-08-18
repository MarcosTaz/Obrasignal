import sqlite3

from latency_metrics import ensure_latency_table, record_stage, latency_snapshot, latency_summary


def test_latency_records_stage_and_summary():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_latency_table(conn)
    record_stage(conn, 'TED', 'fetch', '2026-08-18T19:00:00+00:00', 420, 12)
    record_stage(conn, 'TED', 'fetch', '2026-08-18T19:01:00+00:00', 180, 5)
    rows = latency_snapshot(conn, 'TED')
    assert len(rows) == 2
    assert rows[0]['duration_ms'] == 180
    assert rows[0]['items'] == 5
    summary = latency_summary(conn, 'TED')
    assert summary == [{'stage': 'fetch', 'samples': 2, 'avg_ms': 300.0, 'max_ms': 420}]
