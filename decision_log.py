import json
from datetime import datetime, timezone

SCHEMA = '''CREATE TABLE IF NOT EXISTS opportunity_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL DEFAULT 'default',
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    score INTEGER,
    features_json TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    decided_at TEXT NOT NULL
)'''

RULE_VERSION = 'commercial-v1'
MAX_DECISION_BATCH_KEYS = 100


def _ensure_account_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)").fetchall()}
    if "account_id" not in cols:
        conn.execute("ALTER TABLE opportunity_decisions ADD COLUMN account_id TEXT NOT NULL DEFAULT 'default'")
        conn.commit()


def ensure_decision_table(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_decisions'").fetchone()
    if not exists:
        conn.execute(SCHEMA)
    _ensure_account_column(conn)
    conn.commit()


def record_decision(conn, source, external_id, decision, reason, score=None, features=None, rule_version=RULE_VERSION, decided_at=None, account_id='default'):
    ensure_decision_table(conn)
    ts = decided_at or datetime.now(timezone.utc).isoformat()
    conn.execute(
        '''INSERT INTO opportunity_decisions
           (account_id, source, external_id, decision, reason, score, features_json, rule_version, decided_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (str(account_id or 'default'), source, external_id, decision, reason, score,
         json.dumps(features or {}, ensure_ascii=False, sort_keys=True), rule_version, ts),
    )
    conn.commit()


def _decode_decision_row(row):
    if row is None:
        return None
    item = dict(row)
    item['features'] = json.loads(item.pop('features_json') or '{}')
    return item


def latest_decision(conn, source, external_id, account_id='default'):
    ensure_decision_table(conn)
    row = conn.execute(
        '''SELECT * FROM opportunity_decisions
           WHERE account_id=? AND source=? AND external_id=?
           ORDER BY id DESC LIMIT 1''',
        (str(account_id or 'default'), source, external_id),
    ).fetchone()
    return _decode_decision_row(row)


def latest_decisions(conn, opportunity_keys, account_id='default'):
    """Return latest account-scoped decisions for one bounded Radar-sized key set."""
    keys = []
    seen = set()
    for source, external_id in opportunity_keys or []:
        key = (str(source or ''), str(external_id or ''))
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    if not keys:
        return {}
    if len(keys) > MAX_DECISION_BATCH_KEYS:
        raise ValueError(f"decision batch exceeds bounded limit {MAX_DECISION_BATCH_KEYS}")

    ensure_decision_table(conn)
    values_sql = ",".join("(?, ?)" for _ in keys)
    params = []
    for source, external_id in keys:
        params.extend((source, external_id))
    account = str(account_id or 'default')
    params.extend((account, account))
    rows = conn.execute(
        f'''WITH requested(source, external_id) AS (VALUES {values_sql}),
                latest AS (
                    SELECT od.source, od.external_id, MAX(od.id) AS max_id
                    FROM opportunity_decisions od
                    JOIN requested r
                      ON r.source=od.source AND r.external_id=od.external_id
                    WHERE od.account_id=?
                    GROUP BY od.source, od.external_id
                )
            SELECT d.*
            FROM opportunity_decisions d
            JOIN latest ON latest.max_id=d.id
            WHERE d.account_id=?''',
        params,
    ).fetchall()
    decoded = {}
    for row in rows:
        item = _decode_decision_row(row)
        decoded[(item['source'], item['external_id'])] = item
    return decoded


def funnel_counts(conn, account_id='default'):
    """Return current funnel state, counting only the latest decision per opportunity."""
    rows = conn.execute(
        '''SELECT d.decision, COUNT(*) AS count
           FROM opportunity_decisions d
           JOIN (
               SELECT source, external_id, MAX(id) AS max_id
               FROM opportunity_decisions
               WHERE account_id=?
               GROUP BY source, external_id
           ) latest ON latest.max_id=d.id
           WHERE d.account_id=?
           GROUP BY d.decision
           ORDER BY d.decision''',
        (str(account_id or 'default'), str(account_id or 'default')),
    ).fetchall()
    return {row['decision']: row['count'] for row in rows}
    ensure_decision_table(conn)
