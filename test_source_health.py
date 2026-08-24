from datetime import datetime, timezone, timedelta
import sqlite3

from source_health import ensure_source_health, record_source_result, source_health_snapshot


def _conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def test_source_health_records_success_and_staleness():
    conn = _conn()
    record_source_result(conn, 'TED', success=True, duration_ms=420, found=12, new_items=3)
    row = source_health_snapshot(conn)[0]
    assert row['source'] == 'TED'
    assert row['status'] == 'healthy'
    assert row['last_found'] == 12
    assert row['last_new_items'] == 3
    assert row['last_duration_ms'] == 420
    assert row['stale_after_minutes'] == 60
    assert row['expected_refresh_minutes'] == 15


def test_source_health_records_failure_without_erasing_last_success():
    conn = _conn()
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=4, new_items=1)
    previous = conn.execute('SELECT last_success FROM source_health WHERE source=?', ('TED',)).fetchone()['last_success']
    record_source_result(conn, 'TED', success=False, duration_ms=5000, error='503 Service Unavailable')
    row = source_health_snapshot(conn)[0]
    assert row['status'] == 'degraded'
    assert row['last_error'] == '503 Service Unavailable'
    assert row['last_success'] == previous


def test_daily_source_is_not_falsely_stale_after_one_hour():
    conn = _conn()
    record_source_result(conn, 'LV_IUB', success=True, duration_ms=100, found=10)
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (one_hour_ago, one_hour_ago, 'LV_IUB'))
    conn.commit()
    row = source_health_snapshot(conn)[0]
    assert row['status'] == 'healthy'
    assert row['stale_after_minutes'] == 4320


def test_mutable_monthly_rhr_feed_uses_daily_health_contract():
    conn = _conn()
    record_source_result(conn, 'EE_RHR', success=True, duration_ms=100, found=10)
    twenty_days_ago = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (twenty_days_ago, twenty_days_ago, 'EE_RHR'))
    conn.commit()
    row = source_health_snapshot(conn)[0]
    assert row['status'] == 'stale'
    assert row['expected_refresh_minutes'] == 1440
    assert row['stale_after_minutes'] == 4320


def test_registered_realtime_source_becomes_stale_at_its_own_threshold():
    conn = _conn()
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=10)
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (two_hours_ago, two_hours_ago, 'TED'))
    conn.commit()
    row = source_health_snapshot(conn)[0]
    assert row['status'] == 'stale'
    assert row['stale_after_minutes'] == 60


def test_unregistered_source_keeps_compatibility_fallback():
    conn = _conn()
    record_source_result(conn, 'CUSTOM', success=True, duration_ms=100, found=1)
    twenty_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (twenty_minutes_ago, twenty_minutes_ago, 'CUSTOM'))
    conn.commit()
    row = source_health_snapshot(conn, stale_after_minutes=15)[0]
    assert row['status'] == 'stale'
    assert row['stale_after_minutes'] == 15
    assert row['expected_refresh_minutes'] is None
