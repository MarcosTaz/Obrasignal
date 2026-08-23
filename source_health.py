from datetime import datetime, timezone

from source_registry import SOURCES, stale_after_minutes_for


def ensure_source_health(conn):
    health_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_health'").fetchone()
    if not health_exists:
        conn.execute('''CREATE TABLE IF NOT EXISTS source_health (
        source TEXT PRIMARY KEY,
        last_attempt TEXT,
        last_success TEXT,
        last_error TEXT,
        last_duration_ms INTEGER,
        last_found INTEGER DEFAULT 0,
        last_new_items INTEGER DEFAULT 0,
        status TEXT DEFAULT 'unknown'
    )''')
    cursor_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_cursor'").fetchone()
    if not cursor_exists:
        conn.execute('''CREATE TABLE IF NOT EXISTS source_cursor (
        source TEXT PRIMARY KEY,
        watermark TEXT,
        updated_at TEXT
    )''')
    conn.commit()


def record_source_result(conn, source, *, success, duration_ms, found=0, new_items=0, error=None):
    ensure_source_health(conn)
    now = datetime.now(timezone.utc).isoformat()
    status = 'healthy' if success else 'degraded'
    conn.execute('''INSERT INTO source_health
        (source,last_attempt,last_success,last_error,last_duration_ms,last_found,last_new_items,status)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET
          last_attempt=excluded.last_attempt,
          last_success=CASE WHEN excluded.last_success IS NOT NULL THEN excluded.last_success ELSE source_health.last_success END,
          last_error=excluded.last_error,
          last_duration_ms=excluded.last_duration_ms,
          last_found=excluded.last_found,
          last_new_items=excluded.last_new_items,
          status=excluded.status''',
        (source, now, now if success else None, None if success else str(error), int(duration_ms), int(found), int(new_items), status))
    conn.commit()


def get_source_cursor(conn, source):
    ensure_source_health(conn)
    row = conn.execute('SELECT watermark FROM source_cursor WHERE source=?', (source,)).fetchone()
    return row['watermark'] if row else None


def set_source_cursor(conn, source, watermark):
    ensure_source_health(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute('''INSERT INTO source_cursor(source,watermark,updated_at)
                    VALUES(?,?,?)
                    ON CONFLICT(source) DO UPDATE SET
                      watermark=excluded.watermark,
                      updated_at=excluded.updated_at''',
                 (source, watermark, now))
    conn.commit()


def _source_freshness_metadata(source, default_stale_after_minutes):
    meta = SOURCES.get(source, {})
    stale_after = stale_after_minutes_for(source, default_stale_after_minutes)
    expected_refresh = meta.get('expected_refresh_minutes')
    return stale_after, expected_refresh


def source_health_snapshot(conn, stale_after_minutes=15):
    """Return source health using each source's own freshness SLA.

    ``stale_after_minutes`` remains as a compatibility fallback for unregistered
    sources. Registered sources use ``source_registry.SOURCES`` so daily,
    weekly/monthly or quarterly feeds are not falsely marked stale by the old
    one-size-fits-all 15-minute threshold.
    """
    ensure_source_health(conn)
    rows = conn.execute('SELECT * FROM source_health ORDER BY source').fetchall()
    now = datetime.now(timezone.utc)
    out = []
    for row in rows:
        item = dict(row)
        ref = item.get('last_success') or item.get('last_attempt')
        if ref:
            try:
                age = (now - datetime.fromisoformat(ref.replace('Z','+00:00'))).total_seconds() / 60
            except Exception:
                age = None
        else:
            age = None

        source_stale_after, expected_refresh = _source_freshness_metadata(
            item['source'], stale_after_minutes
        )
        if item['status'] == 'healthy' and age is not None and age > source_stale_after:
            item['status'] = 'stale'

        item['age_minutes'] = round(age, 1) if age is not None else None
        item['stale_after_minutes'] = source_stale_after
        item['expected_refresh_minutes'] = expected_refresh
        cursor = conn.execute('SELECT watermark FROM source_cursor WHERE source=?', (item['source'],)).fetchone()
        item['watermark'] = cursor['watermark'] if cursor else None
        out.append(item)
    return out
