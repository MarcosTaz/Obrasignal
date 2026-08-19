from datetime import datetime, timezone

STATUSES = ("NEW", "REVIEWING", "PREPARING", "SUBMITTED", "WON", "LOST")

SCHEMA = '''
CREATE TABLE IF NOT EXISTS opportunity_workflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, source, external_id)
)
'''


def ensure_workflow_table(conn):
    conn.execute(SCHEMA)
    conn.commit()


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_workflow(conn, account_id, source, external_id):
    ensure_workflow_table(conn)
    row = conn.execute(
        '''SELECT account_id, source, external_id, status, note, updated_at
           FROM opportunity_workflow
           WHERE account_id=? AND source=? AND external_id=?''',
        (str(account_id or "default"), source, external_id),
    ).fetchone()
    if row is None:
        return {"account_id": str(account_id or "default"), "source": source, "external_id": external_id,
                "status": "NEW", "note": None, "updated_at": None}
    return dict(row)


def set_workflow(conn, account_id, source, external_id, status, note=None):
    status = str(status or "").upper()
    if status not in STATUSES:
        raise ValueError(f"invalid workflow status: {status}")
    ensure_workflow_table(conn)
    account_id = str(account_id or "default")
    ts = _now()
    conn.execute(
        '''INSERT INTO opportunity_workflow(account_id, source, external_id, status, note, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(account_id, source, external_id)
           DO UPDATE SET status=excluded.status, note=excluded.note, updated_at=excluded.updated_at''',
        (account_id, source, external_id, status, note, ts),
    )
    conn.commit()
    return get_workflow(conn, account_id, source, external_id)
