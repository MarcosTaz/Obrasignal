from datetime import datetime, timezone, timedelta
import sqlite3

from source_health import ensure_source_health, record_source_result, source_health_snapshot


def test_source_health_records_success_and_staleness():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    record_source_result(conn, 'TED', success=True, duration_ms=420, found=12, new_items=3)
    row = source_health_snapshot(conn)[0]
    assert row['source'] == 'TED'
    assert row['status'] == 'healthy'
    assert row['last_found'] == 12
    assert row['last_new_items'] == 3
    assert row['last_duration_ms'] == 420


def test_source_health_records_failure_without_erasing_last_success():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=4, new_items=1)
    previous = conn.execute('SELECT last_success FROM source_health WHERE source=?', ('TED',)).fetchone()['last_success']
    record_source_result(conn, 'TED', success=False, duration_ms=5000, error='503 Service Unavailable')
    row = source_health_snapshot(conn)[0]
    assert row['status'] == 'degraded'
    assert row['last_error'] == '503 Service Unavailable'
    assert row['last_success'] == previous
