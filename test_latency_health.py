import sqlite3

from latency_metrics import ensure_latency_table, record_stage
from latency_health import latency_health


def test_latency_health_flags_degradation():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_latency_table(conn)
    for i in range(5):
        record_stage(conn, 'TED', 'fetch', f'2026-08-18T19:0{i}:00+00:00', 100, 1)
    for i in range(2):
        record_stage(conn, 'TED', 'fetch', f'2026-08-18T20:0{i}:00+00:00', 450, 1)
    result = latency_health(conn, 'TED', recent_limit=2, baseline_limit=7)
    assert result[0]['stage'] == 'fetch'
    assert result[0]['status'] == 'critical'
    assert result[0]['ratio'] == 4.5
