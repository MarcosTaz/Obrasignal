from datetime import datetime, timezone

from source_registry import SOURCES, stale_after_minutes_for


def _utc_iso(value=None):
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("source health timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def ensure_source_health(conn, *, commit=True):
    health_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_health'").fetchone()
    if not health_exists:
        conn.execute('''CREATE TABLE IF NOT EXISTS source_health (
        source TEXT PRIMARY KEY,
        last_attempt TEXT,
        last_success TEXT,
        last_failed TEXT,
        consecutive_failures INTEGER DEFAULT 0,
        last_error TEXT,
        last_duration_ms INTEGER,
        last_found INTEGER DEFAULT 0,
        last_new_items INTEGER DEFAULT 0,
        status TEXT DEFAULT 'unknown'
    )''')
    else:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(source_health)").fetchall()}
        if 'last_failed' not in columns:
            conn.execute("ALTER TABLE source_health ADD COLUMN last_failed TEXT")
        if 'consecutive_failures' not in columns:
            conn.execute("ALTER TABLE source_health ADD COLUMN consecutive_failures INTEGER DEFAULT 0")
    cursor_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_cursor'").fetchone()
    if not cursor_exists:
        conn.execute('''CREATE TABLE IF NOT EXISTS source_cursor (
        source TEXT PRIMARY KEY,
        watermark TEXT,
        updated_at TEXT
    )''')
    if commit:
        conn.commit()


def record_source_result(conn, source, *, success, duration_ms, found=0, new_items=0, error=None, observed_at=None):
    ensure_source_health(conn)
    now = _utc_iso(observed_at)
    status = 'healthy' if success else 'degraded'
    conn.execute('''INSERT INTO source_health
        (source,last_attempt,last_success,last_failed,consecutive_failures,last_error,last_duration_ms,last_found,last_new_items,status)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET
          last_attempt=excluded.last_attempt,
          last_success=CASE WHEN excluded.last_success IS NOT NULL THEN excluded.last_success ELSE source_health.last_success END,
          last_failed=CASE WHEN excluded.last_failed IS NOT NULL THEN excluded.last_failed ELSE source_health.last_failed END,
          consecutive_failures=CASE WHEN excluded.last_success IS NOT NULL THEN 0 ELSE COALESCE(source_health.consecutive_failures,0)+1 END,
          last_error=excluded.last_error,
          last_duration_ms=excluded.last_duration_ms,
          last_found=excluded.last_found,
          last_new_items=excluded.last_new_items,
          status=excluded.status''',
        (
            source,
            now,
            now if success else None,
            None if success else now,
            0 if success else 1,
            None if success else str(error),
            int(duration_ms),
            int(found),
            int(new_items),
            status,
        ))
    conn.commit()


def get_source_cursor(conn, source):
    ensure_source_health(conn)
    row = conn.execute('SELECT watermark FROM source_cursor WHERE source=?', (source,)).fetchone()
    return row['watermark'] if row else None


def set_source_cursor(conn, source, watermark, *, commit=True, observed_at=None):
    ensure_source_health(conn, commit=False)
    now = _utc_iso(observed_at)
    conn.execute('''INSERT INTO source_cursor(source,watermark,updated_at)
                    VALUES(?,?,?)
                    ON CONFLICT(source) DO UPDATE SET
                      watermark=excluded.watermark,
                      updated_at=excluded.updated_at''',
                 (source, watermark, now))
    if commit:
        conn.commit()


def _source_freshness_metadata(source, default_stale_after_minutes):
    meta = SOURCES.get(source, {})
    stale_after = stale_after_minutes_for(source, default_stale_after_minutes)
    expected_refresh = meta.get('expected_refresh_minutes')
    return stale_after, expected_refresh


def source_health_snapshot(conn, stale_after_minutes=15, *, now=None):
    """Return connector observability using each source's own fetch SLA.

    This compatibility read model reports whether ObraSignal is still observing a
    source on schedule. It does not classify individual opportunity freshness.
    """
    ensure_source_health(conn)
    rows = conn.execute('SELECT * FROM source_health ORDER BY source').fetchall()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    out = []
    for row in rows:
        item = dict(row)
        ref = item.get('last_success') or item.get('last_attempt')
        if ref:
            try:
                parsed = datetime.fromisoformat(ref.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    age = None
                else:
                    age = (now - parsed.astimezone(timezone.utc)).total_seconds() / 60
                    if age < 0:
                        age = None
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
