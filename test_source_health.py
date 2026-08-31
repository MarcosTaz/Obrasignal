from datetime import datetime, timezone, timedelta
import sqlite3

from source_health import (
    empty_result_context,
    ensure_source_health,
    record_source_result,
    source_health_contract,
    source_health_snapshot,
)


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
    assert row['freshness'] == 'fresh'
    assert row['health'] == 'healthy'
    assert row['last_found'] == 12
    assert row['last_new_items'] == 3
    assert row['last_duration_ms'] == 420
    assert row['stale_after_minutes'] == 60
    assert row['expected_refresh_minutes'] == 15


def test_source_health_records_failure_without_erasing_last_success_or_counts():
    conn = _conn()
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=4, new_items=1)
    previous = conn.execute('SELECT last_success FROM source_health WHERE source=?', ('TED',)).fetchone()['last_success']
    record_source_result(conn, 'TED', success=False, duration_ms=5000, error='503 Service Unavailable')
    row = source_health_snapshot(conn)[0]
    assert row['status'] == 'degraded'
    assert row['health'] == 'degraded'
    assert row['stats_state'] == 'stale'
    assert row['last_error'] == '503 Service Unavailable'
    assert row['last_success'] == previous
    assert row['last_found'] == 4
    assert row['last_new_items'] == 1


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
    assert row['freshness'] == 'stale'
    assert row['health'] == 'degraded'
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
    assert row['freshness'] == 'stale'
    assert row['stale_after_minutes'] == 60


def test_unregistered_source_keeps_compatibility_fallback():
    conn = _conn()
    record_source_result(conn, 'CUSTOM', success=True, duration_ms=100, found=1)
    twenty_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (twenty_minutes_ago, twenty_minutes_ago, 'CUSTOM'))
    conn.commit()
    row = source_health_snapshot(conn, stale_after_minutes=15)[0]
    assert row['status'] == 'stale'
    assert row['freshness'] == 'stale'
    assert row['stale_after_minutes'] == 15
    assert row['expected_refresh_minutes'] is None


def test_contract_distinguishes_fresh_aging_stale_and_unknown_per_source():
    conn = _conn()
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=8, observed_at=now - timedelta(minutes=10))

    item = source_health_contract(conn, sources=['TED'], now=now)['items'][0]
    assert item['freshness'] == 'fresh'
    assert item['health'] == 'healthy'
    assert item['stats_state'] == 'current'

    aging_at = (now - timedelta(minutes=30)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (aging_at, aging_at, 'TED'))
    conn.commit()
    item = source_health_contract(conn, sources=['TED'], now=now)['items'][0]
    assert item['freshness'] == 'aging'
    assert item['health'] == 'healthy'
    assert item['stats_state'] == 'aging'

    stale_at = (now - timedelta(minutes=61)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (stale_at, stale_at, 'TED'))
    conn.commit()
    item = source_health_contract(conn, sources=['TED'], now=now)['items'][0]
    assert item['freshness'] == 'stale'
    assert item['health'] == 'degraded'
    assert item['stats_state'] == 'stale'

    missing = source_health_contract(conn, sources=['BASE'], now=now)['items'][0]
    assert missing['freshness'] == 'unknown'
    assert missing['health'] == 'unknown'
    assert missing['stats_state'] == 'unknown'


def test_persistent_failures_become_unavailable_only_after_bounded_evidence():
    conn = _conn()
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=9, observed_at=now - timedelta(hours=2))
    for minutes in (10, 5, 0):
        record_source_result(
            conn,
            'TED',
            success=False,
            duration_ms=5000,
            error='upstream unavailable',
            observed_at=now - timedelta(minutes=minutes),
        )

    item = source_health_contract(conn, sources=['TED'], now=now)['items'][0]
    assert item['freshness'] == 'stale'
    assert item['health'] == 'unavailable'
    assert item['stats_state'] == 'stale'
    assert item['consecutive_failures'] == 3
    assert item['last_found'] == 9


def test_empty_result_contract_never_promotes_empty_to_market_absence():
    conn = _conn()
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    record_source_result(conn, 'TED', success=True, duration_ms=100, found=0, observed_at=now - timedelta(minutes=5))
    fresh_contract = source_health_contract(conn, sources=['TED'], now=now)
    fresh_empty = empty_result_context(fresh_contract, 0)
    assert fresh_empty['state'] == 'observed_empty_current'
    assert fresh_empty['market_absence_proven'] is False
    assert fresh_empty['zero_market_claim_allowed'] is False

    stale_at = (now - timedelta(hours=2)).isoformat()
    conn.execute('UPDATE source_health SET last_success=?, last_attempt=? WHERE source=?', (stale_at, stale_at, 'TED'))
    conn.commit()
    stale_contract = source_health_contract(conn, sources=['TED'], now=now)
    stale_empty = empty_result_context(stale_contract, 0)
    assert stale_empty['state'] == 'coverage_unconfirmed'
    assert stale_empty['coverage_status'] == 'degraded'
    assert stale_empty['zero_market_claim_allowed'] is False


def test_source_failure_does_not_delete_historical_opportunities():
    conn = _conn()
    conn.execute('CREATE TABLE tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT)')
    conn.execute("INSERT INTO tenders VALUES (1, 'TED', 'historic-1', 'Historical opportunity')")
    conn.commit()

    record_source_result(conn, 'TED', success=True, duration_ms=100, found=1)
    record_source_result(conn, 'TED', success=False, duration_ms=5000, error='timeout')

    retained = conn.execute("SELECT source, external_id, title FROM tenders WHERE id=1").fetchone()
    assert dict(retained) == {
        'source': 'TED',
        'external_id': 'historic-1',
        'title': 'Historical opportunity',
    }


def test_legacy_source_health_schema_migrates_without_losing_existing_row():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE source_health (
        source TEXT PRIMARY KEY,
        last_attempt TEXT,
        last_success TEXT,
        last_error TEXT,
        last_duration_ms INTEGER,
        last_found INTEGER DEFAULT 0,
        last_new_items INTEGER DEFAULT 0,
        status TEXT DEFAULT 'unknown'
    )''')
    conn.execute("INSERT INTO source_health VALUES ('TED', '2026-08-25T10:00:00+00:00', '2026-08-25T10:00:00+00:00', NULL, 100, 7, 2, 'healthy')")
    conn.commit()

    ensure_source_health(conn)
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(source_health)').fetchall()}
    row = conn.execute("SELECT * FROM source_health WHERE source='TED'").fetchone()
    assert {'last_failed', 'consecutive_failures'} <= columns
    assert row['last_found'] == 7
    assert row['last_new_items'] == 2
