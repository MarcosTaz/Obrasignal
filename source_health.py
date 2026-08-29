from datetime import datetime, timezone

from normalization_provenance import ensure_normalization_provenance
from source_registry import SOURCES, stale_after_minutes_for


SOURCE_HEALTH_CONTRACT_VERSION = "source-health-v1"
UNAVAILABLE_AFTER_FAILURES = 3


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
    ensure_normalization_provenance(conn)
    if commit:
        conn.commit()


def record_source_result(conn, source, *, success, duration_ms, found=0, new_items=0, error=None, observed_at=None):
    """Record connector observability without turning a failed fetch into a zero result.

    Counts belong to the last successful source observation. A failed attempt marks
    health as degraded and increments the failure streak, but retains the previous
    successful counts and source data so callers can label them stale rather than
    misrepresenting failure as an empty market.
    """
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
          last_found=CASE WHEN excluded.last_success IS NOT NULL THEN excluded.last_found ELSE source_health.last_found END,
          last_new_items=CASE WHEN excluded.last_success IS NOT NULL THEN excluded.last_new_items ELSE source_health.last_new_items END,
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


def record_source_ingestion_failure(conn, source, *, error, observed_at=None):
    """Degrade source currentness after canonical persistence rolls back.

    Fetch success and durable ingestion are distinct evidence. Preserve the prior
    successful fetch timestamp/counts for diagnosis, but record a bounded failure
    observation and degraded status so the public Source Health contract cannot
    mistake successful transport for committed source state.
    """
    ensure_source_health(conn)
    now = _utc_iso(observed_at)
    conn.execute('''INSERT INTO source_health
        (source,last_attempt,last_success,last_failed,consecutive_failures,last_error,last_duration_ms,last_found,last_new_items,status)
        VALUES(?,?,NULL,?,1,?,NULL,0,0,'degraded')
        ON CONFLICT(source) DO UPDATE SET
          last_attempt=excluded.last_attempt,
          last_failed=excluded.last_failed,
          consecutive_failures=COALESCE(source_health.consecutive_failures,0)+1,
          last_error=excluded.last_error,
          status='degraded' ''',
        (str(source), now, now, f"ingestion_commit_failed:{type(error).__name__}"))
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


def _age_minutes(value, *, now):
    if not value:
        return None, None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None, 'invalid_timestamp'
    if parsed.tzinfo is None:
        return None, 'invalid_timestamp'
    age = (now - parsed.astimezone(timezone.utc)).total_seconds() / 60
    if age < 0:
        return None, 'future_timestamp'
    return age, None


def _failure_count(item):
    try:
        failures = int(item.get('consecutive_failures') or 0)
    except (TypeError, ValueError):
        return None
    if failures < 0:
        return None
    if failures == 0 and item.get('status') == 'degraded':
        return 1
    return failures


def _public_error_category(value):
    """Return a stable public diagnostic without echoing upstream error text.

    Internal source-health persistence intentionally retains raw failure evidence
    for operators. The public/customer-facing contract is a separate trust
    boundary: urllib/provider exceptions can contain bearer material, signed
    URLs, query credentials, or provider payloads, so only bounded categories
    may cross it.
    """
    if value in (None, ''):
        return None
    text = str(value)
    if text.startswith('ingestion_commit_failed:'):
        return 'ingestion_commit_failed'
    if text.startswith('production gate blocked:'):
        return 'production_gate_blocked'
    if text == 'BASE_ACCESS_TOKEN is not configured':
        return 'source_not_configured'
    return 'upstream_failure'


def _derive_source_state(item, *, now, default_stale_after_minutes=15):
    source = item['source']
    stale_after, expected_refresh = _source_freshness_metadata(source, default_stale_after_minutes)
    success_age, timestamp_error = _age_minutes(item.get('last_success'), now=now)
    failures = _failure_count(item)
    reasons = []

    if timestamp_error:
        freshness = 'unknown'
        health = 'unknown'
        reasons.append(timestamp_error)
    else:
        if success_age is None:
            freshness = 'unknown'
            reasons.append('no_success_observation')
        elif expected_refresh is not None and success_age <= int(expected_refresh):
            freshness = 'fresh'
        elif success_age <= stale_after:
            freshness = 'aging'
            reasons.append('expected_refresh_missed')
        else:
            freshness = 'stale'
            reasons.append('source_refresh_overdue')

        if failures is None:
            health = 'unknown'
            reasons.append('invalid_failure_counter')
        elif failures >= UNAVAILABLE_AFTER_FAILURES and (success_age is None or success_age > stale_after):
            health = 'unavailable'
            reasons.append('persistent_source_failure')
        elif failures > 0:
            health = 'degraded'
            reasons.append('source_attempt_failed')
        elif success_age is None:
            health = 'unknown'
        elif success_age > stale_after:
            health = 'degraded'
            reasons.append('source_observation_overdue')
        else:
            health = 'healthy'

    if item.get('last_success') is None:
        stats_state = 'unknown'
    elif health in ('degraded', 'unavailable') or freshness == 'stale':
        stats_state = 'stale'
    elif freshness == 'aging':
        stats_state = 'aging'
    elif freshness == 'fresh' and health == 'healthy':
        stats_state = 'current'
    else:
        stats_state = 'unknown'

    return {
        'freshness': freshness,
        'health': health,
        'stats_state': stats_state,
        'age_minutes': round(success_age, 1) if success_age is not None else None,
        'stale_after_minutes': stale_after,
        'expected_refresh_minutes': expected_refresh,
        'reason_codes': tuple(dict.fromkeys(reasons)),
    }


def source_health_snapshot(conn, stale_after_minutes=15, *, now=None):
    """Compatibility snapshot for sources that already have observability rows.

    ``status`` is a legacy compatibility field and must never remain stronger than
    the derived freshness/health authority. New consumers should use the additive
    ``freshness`` and ``health`` fields directly. This operator-facing snapshot
    retains raw diagnostic evidence; public callers must use source_health_contract.
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
        state = _derive_source_state(item, now=now, default_stale_after_minutes=stale_after_minutes)
        if item['status'] == 'healthy':
            failures = _failure_count(item)
            if state['freshness'] == 'unknown' or state['health'] == 'unknown':
                item['status'] = 'unknown'
            elif state['health'] == 'unavailable':
                item['status'] = 'unavailable'
            elif state['health'] == 'degraded' and failures not in (None, 0):
                item['status'] = 'degraded'
            elif state['freshness'] == 'stale':
                item['status'] = 'stale'
            elif state['health'] != 'healthy':
                item['status'] = state['health']
        item.update(state)
        cursor = conn.execute('SELECT watermark FROM source_cursor WHERE source=?', (item['source'],)).fetchone()
        item['watermark'] = cursor['watermark'] if cursor else None
        out.append(item)
    return out


def source_health_contract(conn, *, sources=None, now=None, stale_after_minutes=15):
    """Return the canonical public source-health/freshness contract.

    Missing registered sources are explicit ``unknown`` entries rather than being
    silently absent. Coverage expectations are derived only from registry sources
    whose runtime status is ``active``; ``ready`` or ``planned`` sources are shown
    for truth but do not falsely count as current ingestion coverage. Raw upstream
    error strings never cross this public boundary.
    """
    ensure_source_health(conn)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)

    rows = {row['source']: dict(row) for row in conn.execute('SELECT * FROM source_health').fetchall()}
    if sources is None:
        names = sorted(set(SOURCES) | set(rows))
    else:
        names = sorted({str(source).strip() for source in sources if str(source).strip()})

    items = []
    for source in names:
        item = rows.get(source, {
            'source': source,
            'last_attempt': None,
            'last_success': None,
            'last_failed': None,
            'consecutive_failures': 0,
            'last_error': None,
            'last_duration_ms': None,
            'last_found': 0,
            'last_new_items': 0,
            'status': 'unknown',
        })
        state = _derive_source_state(item, now=now, default_stale_after_minutes=stale_after_minutes)
        meta = SOURCES.get(source, {})
        cursor = conn.execute('SELECT watermark FROM source_cursor WHERE source=?', (source,)).fetchone()
        items.append({
            'source': source,
            'runtime_status': meta.get('status', 'unknown'),
            'country': meta.get('country'),
            'coverage_expected': meta.get('status') == 'active',
            'freshness': state['freshness'],
            'health': state['health'],
            'stats_state': state['stats_state'],
            'age_minutes': state['age_minutes'],
            'expected_refresh_minutes': state['expected_refresh_minutes'],
            'stale_after_minutes': state['stale_after_minutes'],
            'last_attempt': item.get('last_attempt'),
            'last_success': item.get('last_success'),
            'last_failed': item.get('last_failed'),
            'consecutive_failures': _failure_count(item),
            'last_error': _public_error_category(item.get('last_error')),
            'last_duration_ms': item.get('last_duration_ms'),
            'last_found': item.get('last_found'),
            'last_new_items': item.get('last_new_items'),
            'watermark': cursor['watermark'] if cursor else None,
            'reason_codes': list(state['reason_codes']),
        })

    expected = [item for item in items if item['coverage_expected']]
    all_current = bool(expected) and all(
        item['freshness'] == 'fresh' and item['health'] == 'healthy' for item in expected
    )
    if not expected:
        coverage_status = 'unknown'
    elif any(item['health'] == 'unavailable' for item in expected):
        coverage_status = 'unavailable'
    elif any(item['health'] == 'degraded' or item['freshness'] == 'stale' for item in expected):
        coverage_status = 'degraded'
    elif any(item['freshness'] == 'unknown' or item['health'] == 'unknown' for item in expected):
        coverage_status = 'unknown'
    elif any(item['freshness'] == 'aging' for item in expected):
        coverage_status = 'aging'
    else:
        coverage_status = 'current'

    return {
        'contract_version': SOURCE_HEALTH_CONTRACT_VERSION,
        'generated_at': now.isoformat(),
        'scope': 'registered_sources',
        'coverage_scope': 'active_sources',
        'items': items,
        'summary': {
            'expected_source_count': len(expected),
            'observed_expected_source_count': sum(item['last_success'] is not None for item in expected),
            'coverage_status': coverage_status,
            'all_expected_sources_current': all_current,
            'market_absence_proven': False,
            'zero_market_claim_allowed': False,
        },
    }


def empty_result_context(health_contract, item_count):
    """Bound an empty list to observed data; never promote it to market absence."""
    count = max(0, int(item_count or 0))
    summary = (health_contract or {}).get('summary') or {}
    if count:
        state = 'has_results'
    elif summary.get('all_expected_sources_current'):
        state = 'observed_empty_current'
    else:
        state = 'coverage_unconfirmed'
    return {
        'state': state,
        'result_count': count,
        'coverage_status': summary.get('coverage_status', 'unknown'),
        'all_expected_sources_current': bool(summary.get('all_expected_sources_current')),
        'market_absence_proven': False,
        'zero_market_claim_allowed': False,
    }
