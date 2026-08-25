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
MAX_FEATURES_JSON_BYTES = 512_000


def _account_id(value):
    account_id = str(value or '').strip()
    if not account_id:
        raise ValueError('account_id is required')
    return account_id


def _encode_features(features):
    raw = json.dumps(features or {}, ensure_ascii=False, sort_keys=True)
    if len(raw.encode('utf-8')) > MAX_FEATURES_JSON_BYTES:
        raise ValueError('decision features exceed maximum serialized size')
    return raw


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
    tenant = _account_id(account_id)
    encoded_features = _encode_features(features)
    ts = decided_at or datetime.now(timezone.utc).isoformat()
    conn.execute(
        '''INSERT INTO opportunity_decisions
           (account_id, source, external_id, decision, reason, score, features_json, rule_version, decided_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (tenant, source, external_id, decision, reason, score,
         encoded_features, rule_version, ts),
    )
    conn.commit()


def latest_decision(conn, source, external_id, account_id='default'):
    ensure_decision_table(conn)
    tenant = _account_id(account_id)
    row = conn.execute(
        '''SELECT * FROM opportunity_decisions
           WHERE account_id=? AND source=? AND external_id=?
           ORDER BY id DESC LIMIT 1''',
        (tenant, source, external_id),
    ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item['features'] = json.loads(item.pop('features_json') or '{}')
    return item


def funnel_counts(conn, account_id='default'):
    """Return current funnel state, counting only the latest decision per opportunity."""
    tenant = _account_id(account_id)
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
        (tenant, tenant),
    ).fetchall()
    return {row['decision']: row['count'] for row in rows}
