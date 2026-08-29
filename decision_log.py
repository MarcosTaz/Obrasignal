import hashlib
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
    profile_fingerprint TEXT,
    opportunity_fingerprint TEXT,
    decided_at TEXT NOT NULL
)'''

RULE_VERSION = 'commercial-v1'
_NO_PERSISTED_PROFILE = 'profile:none'
_NO_CANONICAL_OPPORTUNITY = 'opportunity:none'
_DECISION_RELEVANT_OPPORTUNITY_FIELDS = (
    'source',
    'signal_type',
    'external_id',
    'title',
    'description',
    'buyer',
    'country',
    'cpv',
    'value',
    'value_numeric',
    'currency',
    'deadline',
    'procedure_type',
    'notice_type',
    'locations',
)


def _ensure_account_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)").fetchall()}
    if "account_id" not in cols:
        conn.execute("ALTER TABLE opportunity_decisions ADD COLUMN account_id TEXT NOT NULL DEFAULT 'default'")
        conn.commit()


def _ensure_profile_fingerprint_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)").fetchall()}
    if "profile_fingerprint" not in cols:
        conn.execute("ALTER TABLE opportunity_decisions ADD COLUMN profile_fingerprint TEXT")
        conn.commit()


def _ensure_opportunity_fingerprint_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)").fetchall()}
    if "opportunity_fingerprint" not in cols:
        conn.execute("ALTER TABLE opportunity_decisions ADD COLUMN opportunity_fingerprint TEXT")
        conn.commit()


def ensure_decision_table(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_decisions'").fetchone()
    if not exists:
        conn.execute(SCHEMA)
    _ensure_account_column(conn)
    _ensure_profile_fingerprint_column(conn)
    _ensure_opportunity_fingerprint_column(conn)
    conn.commit()


def profile_fingerprint(profile):
    """Return a content-addressed revision for one effective company profile."""
    if not isinstance(profile, dict):
        return None
    canonical = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return 'sha256:' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def current_profile_fingerprint(conn, account_id='default'):
    """Return the authoritative persisted profile fingerprint for one tenant."""
    account = str(account_id or 'default')
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='company_profiles'"
    ).fetchone()
    if table is None:
        return _NO_PERSISTED_PROFILE
    row = conn.execute(
        "SELECT profile_json FROM company_profiles WHERE account_id=?",
        (account,),
    ).fetchone()
    if row is None:
        return _NO_PERSISTED_PROFILE
    raw = row['profile_json'] if hasattr(row, 'keys') else row[0]
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return profile_fingerprint(payload)


def opportunity_fingerprint(record):
    """Hash only canonical opportunity fields that can affect decisioning."""
    if not isinstance(record, dict):
        return None
    snapshot = {field: record.get(field) for field in _DECISION_RELEVANT_OPPORTUNITY_FIELDS}
    canonical = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    )
    return 'sha256:' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def current_opportunity_fingerprint(conn, source, external_id):
    """Return the current canonical decision-relevant opportunity revision.

    No canonical signal snapshot is a deterministic legacy sentinel. A malformed
    canonical snapshot is different: currentness cannot be proved and fails closed.
    """
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='signal_records'"
    ).fetchone()
    if table is None:
        return _NO_CANONICAL_OPPORTUNITY
    row = conn.execute(
        """SELECT normalized_json FROM signal_records
           WHERE source=? AND signal_type='TENDER' AND external_id=?""",
        (str(source or '').strip(), str(external_id or '').strip()),
    ).fetchone()
    if row is None:
        return _NO_CANONICAL_OPPORTUNITY
    raw = row['normalized_json'] if hasattr(row, 'keys') else row[0]
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return opportunity_fingerprint(payload)


def record_decision(conn, source, external_id, decision, reason, score=None, features=None, rule_version=RULE_VERSION, decided_at=None, account_id='default', profile_revision_fingerprint=None, opportunity_revision_fingerprint=None):
    ensure_decision_table(conn)
    ts = decided_at or datetime.now(timezone.utc).isoformat()
    account = str(account_id or 'default')
    bound_profile = profile_revision_fingerprint
    if bound_profile is None:
        bound_profile = current_profile_fingerprint(conn, account)
    bound_opportunity = opportunity_revision_fingerprint
    if bound_opportunity is None:
        bound_opportunity = current_opportunity_fingerprint(conn, source, external_id)
    conn.execute(
        '''INSERT INTO opportunity_decisions
           (account_id, source, external_id, decision, reason, score, features_json, rule_version, profile_fingerprint, opportunity_fingerprint, decided_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (account, source, external_id, decision, reason, score,
         json.dumps(features or {}, ensure_ascii=False, sort_keys=True), rule_version,
         bound_profile, bound_opportunity, ts),
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


def decision_opportunity_is_current(conn, decision):
    """Prove only the canonical opportunity-revision edge for a decision."""
    if not decision:
        return False
    current_opportunity = current_opportunity_fingerprint(
        conn,
        decision.get('source'),
        decision.get('external_id'),
    )
    if current_opportunity is None:
        return False
    return decision.get('opportunity_fingerprint') == current_opportunity


def latest_opportunity_current_decision(conn, source, external_id, account_id='default'):
    """Return latest tenant decision only while opportunity revision is current."""
    decision = latest_decision(conn, source, external_id, account_id=account_id)
    if not decision_opportunity_is_current(conn, decision):
        return None
    return decision


def decision_is_current(conn, decision, *, account_id='default', expected_rule_version):
    """Prove rule, tenant, profile and canonical opportunity currentness."""
    if not decision:
        return False
    account = str(account_id or 'default')
    if str(decision.get('account_id') or 'default') != account:
        return False
    if decision.get('rule_version') != expected_rule_version:
        return False
    current_profile = current_profile_fingerprint(conn, account)
    if current_profile is None or decision.get('profile_fingerprint') != current_profile:
        return False
    return decision_opportunity_is_current(conn, decision)


def latest_current_decision(conn, source, external_id, *, account_id='default', expected_rule_version):
    """Return the latest decision only when every current-authority gate passes."""
    decision = latest_decision(conn, source, external_id, account_id=account_id)
    if not decision_is_current(
        conn,
        decision,
        account_id=account_id,
        expected_rule_version=expected_rule_version,
    ):
        return None
    return decision


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
