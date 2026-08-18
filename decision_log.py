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


def _ensure_account_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)").fetchall()}
    if "account_id" not in cols:
        conn.execute("ALTER TABLE opportunity_decisions ADD COLUMN account_id TEXT NOT NULL DEFAULT 'default'")
        conn.commit()


def ensure_decision_table(conn):
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


def latest_decision(conn, source, external_id, account_id='default'):
    ensure_decision_table(conn)
    row = conn.execute(
        '''SELECT * FROM opportunity_decisions
           WHERE account_id=? AND source=? AND external_id=?
           ORDER BY id DESC LIMIT 1''',
        (str(account_id or 'default'), source, external_id),
    ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item['features'] = json.loads(item.pop('features_json') or '{}')
    return item


def funnel_counts(conn, account_id='default'):
    ensure_decision_table(conn)
    rows = conn.execute(
        '''SELECT decision, COUNT(*) AS count
           FROM opportunity_decisions
           WHERE account_id=?
           GROUP BY decision
           ORDER BY decision''',
        (str(account_id or 'default'),),
    ).fetchall()
    return {row['decision']: row['count'] for row in rows}
