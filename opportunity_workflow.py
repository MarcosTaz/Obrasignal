from datetime import datetime, timezone
import sqlite3

STATUSES = ("NEW", "REVIEWING", "PREPARING", "SUBMITTED", "WON", "LOST")
MAX_WORKFLOW_BATCH_KEYS = 100

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


def _workflow_schema_ready(conn):
    """Probe the exact read schema without acquiring a schema-writer lock."""
    try:
        conn.execute(
            "SELECT account_id,source,external_id,status,note,updated_at "
            "FROM opportunity_workflow LIMIT 0"
        )
        return True
    except sqlite3.OperationalError:
        return False


def ensure_workflow_table(conn):
    # Steady-state customer reads must not run CREATE/commit. Fresh/legacy stores
    # still self-heal, while current production schema takes the read-only probe.
    if _workflow_schema_ready(conn):
        return
    conn.execute(SCHEMA)
    conn.commit()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _default_workflow(account_id, source, external_id):
    return {"account_id": str(account_id or "default"), "source": source, "external_id": external_id,
            "status": "NEW", "note": None, "updated_at": None}


def get_workflow(conn, account_id, source, external_id):
    ensure_workflow_table(conn)
    row = conn.execute(
        '''SELECT account_id, source, external_id, status, note, updated_at
           FROM opportunity_workflow
           WHERE account_id=? AND source=? AND external_id=?''',
        (str(account_id or "default"), source, external_id),
    ).fetchone()
    if row is None:
        return _default_workflow(account_id, source, external_id)
    return dict(row)


def get_workflows(conn, account_id, opportunity_keys):
    """Return bounded account-scoped workflows for one collection read."""
    account_id = str(account_id or "default")
    keys = []
    seen = set()
    for source, external_id in opportunity_keys or []:
        key = (source, external_id)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    if not keys:
        return {}
    if len(keys) > MAX_WORKFLOW_BATCH_KEYS:
        raise ValueError(f"workflow batch exceeds bounded limit {MAX_WORKFLOW_BATCH_KEYS}")

    ensure_workflow_table(conn)
    result = {
        key: _default_workflow(account_id, key[0], key[1])
        for key in keys
    }
    values_sql = ",".join("(?, ?)" for _ in keys)
    params = []
    for source, external_id in keys:
        params.extend((source, external_id))
    params.append(account_id)
    rows = conn.execute(
        f'''WITH requested(source, external_id) AS (VALUES {values_sql})
            SELECT w.account_id, w.source, w.external_id, w.status, w.note, w.updated_at
            FROM opportunity_workflow w
            JOIN requested r
              ON r.source=w.source AND r.external_id=w.external_id
            WHERE w.account_id=?''',
        params,
    ).fetchall()
    for row in rows:
        item = dict(row)
        result[(item["source"], item["external_id"])] = item
    return result


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


def workflow_counts(conn, account_id):
    ensure_workflow_table(conn)
    rows = conn.execute(
        '''SELECT status, COUNT(*) AS count
           FROM opportunity_workflow
           WHERE account_id=?
           GROUP BY status''',
        (str(account_id or "default"),),
    ).fetchall()
    counts = {status: 0 for status in STATUSES}
    counts.update({row["status"]: row["count"] for row in rows})
    return counts
