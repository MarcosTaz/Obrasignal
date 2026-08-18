from datetime import datetime, timezone


def ensure_source_health(conn):
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


def source_health_snapshot(conn, stale_after_minutes=15):
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
        if item['status'] == 'healthy' and age is not None and age > stale_after_minutes:
            item['status'] = 'stale'
        item['age_minutes'] = round(age, 1) if age is not None else None
        out.append(item)
    return out
