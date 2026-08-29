"""Account-scoped opportunity eventing for ObraSignal."""
from datetime import datetime, timezone
import hashlib
import re

from decision_log import latest_current_decision
from decision_relevance import relevant_shortlist_eligible_from_features
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from opportunity_match_pipeline import RULE_VERSION


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _key(row):
    source = _norm(row.get("source"))
    external_id = _norm(row.get("external_id"))
    if external_id:
        return f"{source}:{external_id}"
    raw = "|".join(_norm(row.get(k)) for k in ("title", "buyer", "deadline", "country"))
    return f"fallback:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def ensure_event_table(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_events'").fetchone()
    if not exists:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS opportunity_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL DEFAULT 'default',
                event_key TEXT NOT NULL UNIQUE,
                tender_id INTEGER,
                source TEXT,
                event_type TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            )"""
        )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_events)").fetchall()}
    if "account_id" not in cols:
        conn.execute("ALTER TABLE opportunity_events ADD COLUMN account_id TEXT NOT NULL DEFAULT 'default'")
    conn.commit()


def _current_relevant_decision(conn, account_id, row, min_score):
    """Return the only authority allowed to create customer high-match work.

    Global tender score is not account relevance. New notification work requires
    the tenant's latest decision to be current for rule, profile and canonical
    opportunity revision, explicitly relevant, and above the requested account
    decision-score threshold.
    """
    decision = latest_current_decision(
        conn,
        row.get("source"),
        row.get("external_id"),
        account_id=account_id,
        expected_rule_version=RULE_VERSION,
    )
    if not decision:
        return None
    if not relevant_shortlist_eligible_from_features(decision.get("features")):
        return None
    try:
        score = int(decision.get("score") or 0)
    except (TypeError, ValueError):
        return None
    if score < int(min_score):
        return None
    return decision


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record new, actionable, current and explicitly relevant work for one account."""
    account_id = str(account_id or "default")
    ensure_event_table(conn)
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT t.* FROM tenders t
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE t.first_seen IS NOT NULL
             AND t.first_seen >= datetime('now','-2 minutes')
             AND {actionable_predicate('lc', 't')}
           ORDER BY t.first_seen ASC, t.source ASC, t.external_id ASC"""
    ).fetchall()
    events = []
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        d = dict(row)
        decision = _current_relevant_decision(conn, account_id, d, min_score)
        if decision is None:
            continue
        account_score = int(decision.get("score") or 0)
        base_key = _key(d)
        event_key = f"{account_id}:{base_key}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account_id, event_key, d.get("id"), d.get("source"), "new_high_match", account_score, now),
        )
        if cur.rowcount:
            events.append({
                "event_key": event_key,
                "account_id": account_id,
                "tender_id": d.get("id"),
                "source": d.get("source"),
                "score": account_score,
                "title": d.get("title"),
                "country": d.get("country"),
                "url": d.get("url"),
            })
    conn.commit()
    return events
