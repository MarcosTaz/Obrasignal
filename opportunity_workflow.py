from datetime import datetime, timezone

STATUSES = ("NEW", "REVIEWING", "PREPARING", "SUBMITTED", "DISMISSED", "WON", "LOST")
PRIORITIES = ("LOW", "NORMAL", "HIGH")
NOTE_MAX_LENGTH = 500

SCHEMA = '''
CREATE TABLE IF NOT EXISTS opportunity_workflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    priority TEXT NOT NULL DEFAULT 'NORMAL',
    saved_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, source, external_id)
)
'''


def ensure_workflow_table(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_workflow'").fetchone()
    if not exists:
        conn.execute(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_workflow)").fetchall()}
    if "priority" not in columns:
        conn.execute("ALTER TABLE opportunity_workflow ADD COLUMN priority TEXT NOT NULL DEFAULT 'NORMAL'")
    if "saved_at" not in columns:
        conn.execute("ALTER TABLE opportunity_workflow ADD COLUMN saved_at TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_workflow_account_saved "
        "ON opportunity_workflow(account_id, saved_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_workflow_account_status_priority "
        "ON opportunity_workflow(account_id, status, priority)"
    )
    conn.commit()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _account_id(account_id):
    return str(account_id or "default")


def _validate_note(note):
    if note is None:
        return None
    note = str(note).strip()
    if len(note) > NOTE_MAX_LENGTH:
        raise ValueError(f"note exceeds {NOTE_MAX_LENGTH} characters")
    return note or None


def _validate_status(status):
    status = str(status or "").upper()
    if status not in STATUSES:
        raise ValueError(f"invalid workflow status: {status}")
    return status


def _validate_priority(priority):
    priority = str(priority or "").upper()
    if priority not in PRIORITIES:
        raise ValueError(f"invalid workflow priority: {priority}")
    return priority


def _opportunity_identity(conn, opportunity_id):
    row = conn.execute("SELECT source, external_id FROM tenders WHERE id=?", (opportunity_id,)).fetchone()
    if row is None:
        raise LookupError("opportunity_not_found")
    return row["source"], row["external_id"]


def get_workflow(conn, account_id, source, external_id):
    ensure_workflow_table(conn)
    row = conn.execute(
        '''SELECT account_id, source, external_id, status, note, priority, saved_at, updated_at
           FROM opportunity_workflow
           WHERE account_id=? AND source=? AND external_id=?''',
        (_account_id(account_id), source, external_id),
    ).fetchone()
    if row is None:
        return {"account_id": _account_id(account_id), "source": source, "external_id": external_id,
                "status": "NEW", "note": None, "priority": "NORMAL", "saved_at": None,
                "is_saved": False, "updated_at": None}
    item = dict(row)
    item["is_saved"] = item.get("saved_at") is not None
    return item


def set_workflow(conn, account_id, source, external_id, status, note=None):
    status = _validate_status(status)
    note = _validate_note(note)
    ensure_workflow_table(conn)
    account_id = _account_id(account_id)
    ts = _now()
    conn.execute(
        '''INSERT INTO opportunity_workflow(account_id, source, external_id, status, note, priority, saved_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'NORMAL', NULL, ?)
           ON CONFLICT(account_id, source, external_id)
           DO UPDATE SET status=excluded.status, note=excluded.note, updated_at=excluded.updated_at''',
        (account_id, source, external_id, status, note, ts),
    )
    conn.commit()
    return get_workflow(conn, account_id, source, external_id)


def save_opportunity(conn, account_id, opportunity_id):
    """Atomically and idempotently save a canonical opportunity for one account."""
    ensure_workflow_table(conn)
    source, external_id = _opportunity_identity(conn, opportunity_id)
    account_id = _account_id(account_id)
    ts = _now()
    conn.execute(
        '''INSERT INTO opportunity_workflow(account_id, source, external_id, status, note, priority, saved_at, updated_at)
           VALUES (?, ?, ?, 'NEW', NULL, 'NORMAL', ?, ?)
           ON CONFLICT(account_id, source, external_id)
           DO UPDATE SET
               saved_at=COALESCE(opportunity_workflow.saved_at, excluded.saved_at),
               updated_at=CASE
                   WHEN opportunity_workflow.saved_at IS NULL THEN excluded.updated_at
                   ELSE opportunity_workflow.updated_at
               END''',
        (account_id, source, external_id, ts, ts),
    )
    conn.commit()
    return get_saved_opportunity(conn, account_id, opportunity_id)


def unsave_opportunity(conn, account_id, opportunity_id):
    """Remove watchlist membership while preserving existing workflow state."""
    ensure_workflow_table(conn)
    source, external_id = _opportunity_identity(conn, opportunity_id)
    cur = conn.execute(
        '''UPDATE opportunity_workflow SET saved_at=NULL, updated_at=?
           WHERE account_id=? AND source=? AND external_id=? AND saved_at IS NOT NULL''',
        (_now(), _account_id(account_id), source, external_id),
    )
    conn.commit()
    return bool(cur.rowcount)


def get_saved_opportunity(conn, account_id, opportunity_id):
    ensure_workflow_table(conn)
    source, external_id = _opportunity_identity(conn, opportunity_id)
    row = conn.execute(
        '''SELECT account_id, source, external_id, status, note, priority, saved_at, updated_at
           FROM opportunity_workflow
           WHERE account_id=? AND source=? AND external_id=? AND saved_at IS NOT NULL''',
        (_account_id(account_id), source, external_id),
    ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["opportunity_id"] = opportunity_id
    item["is_saved"] = True
    return item


def update_saved_opportunity(conn, account_id, opportunity_id, *, status=None, priority=None, note=None,
                             note_provided=False):
    ensure_workflow_table(conn)
    source, external_id = _opportunity_identity(conn, opportunity_id)
    account_id = _account_id(account_id)
    current = conn.execute(
        '''SELECT 1 FROM opportunity_workflow
           WHERE account_id=? AND source=? AND external_id=? AND saved_at IS NOT NULL''',
        (account_id, source, external_id),
    ).fetchone()
    if current is None:
        raise LookupError("saved_opportunity_not_found")
    assignments = []
    params = []
    if status is not None:
        assignments.append("status=?")
        params.append(_validate_status(status))
    if priority is not None:
        assignments.append("priority=?")
        params.append(_validate_priority(priority))
    if note_provided:
        assignments.append("note=?")
        params.append(_validate_note(note))
    if not assignments:
        raise ValueError("no supported watchlist fields supplied")
    assignments.append("updated_at=?")
    params.append(_now())
    params.extend([account_id, source, external_id])
    conn.execute(
        f'''UPDATE opportunity_workflow SET {", ".join(assignments)}
            WHERE account_id=? AND source=? AND external_id=? AND saved_at IS NOT NULL''',
        params,
    )
    conn.commit()
    return get_saved_opportunity(conn, account_id, opportunity_id)


def list_saved_opportunities(conn, account_id, *, status=None, priority=None, order="recent", limit=20, offset=0):
    from opportunity_lifecycle import ensure_lifecycle_table

    ensure_workflow_table(conn)
    ensure_lifecycle_table(conn)
    account_id = _account_id(account_id)
    where = ["w.account_id=?", "w.saved_at IS NOT NULL"]
    params = [account_id]
    if status is not None:
        where.append("w.status=?")
        params.append(_validate_status(status))
    if priority is not None:
        where.append("w.priority=?")
        params.append(_validate_priority(priority))
    order_sql = {
        "recent": "w.saved_at DESC, w.id DESC",
        "deadline": "CASE WHEN t.deadline IS NULL OR t.deadline='' THEN 1 ELSE 0 END, t.deadline ASC, w.saved_at DESC, w.id DESC",
        "priority": "CASE w.priority WHEN 'HIGH' THEN 0 WHEN 'NORMAL' THEN 1 ELSE 2 END, w.saved_at DESC, w.id DESC",
    }.get(str(order or "recent").lower())
    if order_sql is None:
        raise ValueError("invalid watchlist order")
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    params.extend([limit, offset])
    rows = conn.execute(
        f'''SELECT w.account_id, w.source, w.external_id, w.status, w.note, w.priority,
                   w.saved_at, w.updated_at, t.id AS opportunity_id, t.title, t.buyer, t.country,
                   t.deadline, t.url, t.score, t.market, t.first_seen, t.last_seen,
                   COALESCE(lc.is_actionable, 1) AS is_actionable,
                   lc.lifecycle_status, lc.lifecycle_reason,
                   lc.source_updated_at AS lifecycle_source_updated_at,
                   lc.last_observed AS lifecycle_last_observed
            FROM opportunity_workflow w
            LEFT JOIN tenders t ON t.source=w.source AND t.external_id=w.external_id
            LEFT JOIN opportunity_lifecycle lc ON lc.source=w.source AND lc.external_id=w.external_id
            WHERE {' AND '.join(where)}
            ORDER BY {order_sql} LIMIT ? OFFSET ?''',
        params,
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["is_saved"] = True
        item["is_actionable"] = bool(item.get("is_actionable"))
        item["opportunity_missing"] = item.get("opportunity_id") is None
        items.append(item)
    return items


def workflow_counts(conn, account_id):
    ensure_workflow_table(conn)
    rows = conn.execute(
        '''SELECT status, COUNT(*) AS count
           FROM opportunity_workflow
           WHERE account_id=?
           GROUP BY status''',
        (_account_id(account_id),),
    ).fetchall()
    counts = {status: 0 for status in STATUSES}
    counts.update({row["status"]: row["count"] for row in rows})
    return counts
