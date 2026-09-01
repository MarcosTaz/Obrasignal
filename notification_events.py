"""Account-scoped opportunity eventing for ObraSignal."""
from datetime import datetime, timezone
import hashlib
import re
import sqlite3

from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _key(row):
    source = _norm(row.get("source"))
    external_id = _norm(row.get("external_id"))
    if external_id:
        return f"{source}:{external_id}"
    raw = "|".join(_norm(row.get(k)) for k in ("title", "buyer", "deadline", "country"))
    return f"fallback:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def event_key_for(account_id, row):
    """Return the one canonical tenant+opportunity identity used by every emitter."""
    return f"{str(account_id or 'default')}:{_key(row)}"


def _event_schema_ready(conn):
    try:
        conn.execute(
            "SELECT account_id,event_key,tender_id,source,event_type,score,created_at,delivered_at "
            "FROM opportunity_events LIMIT 0"
        )
    except sqlite3.OperationalError:
        return False
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name IN "
            "('idx_opportunity_events_account_feed','idx_opportunity_events_account_delivery')"
        ).fetchall()
    }
    return indexes == {
        "idx_opportunity_events_account_feed",
        "idx_opportunity_events_account_delivery",
    }


def ensure_event_table(conn):
    if _event_schema_ready(conn):
        return
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_events_account_feed "
        "ON opportunity_events(account_id, event_type, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_events_account_delivery "
        "ON opportunity_events(account_id, event_type, delivered_at, created_at DESC)"
    )
    conn.commit()


def _latest_completed_sync_window(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_runs'").fetchone()
    if not exists:
        return None, None
    rows = conn.execute(
        "SELECT finished_at FROM sync_runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 2"
    ).fetchall()
    current = rows[0][0] if rows else None
    previous = rows[1][0] if len(rows) > 1 else None
    return current, previous


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record qualified actionable opportunities discovered since the last good sync.

    Account-scoped decisions are the only scoring authority. When production
    ingestion commits tenders in bounded chunks, an interrupted attempt can leave
    correctly persisted new tenders before its sync run is marked complete. The
    next successful run updates ``last_seen`` and this window includes every row
    whose true ``first_seen`` is after the previous completed run, so availability
    hardening cannot silently lose a customer alert.
    """
    account_id = str(account_id or "default")
    ensure_event_table(conn)
    ensure_lifecycle_table(conn)
    current_sync, previous_sync = _latest_completed_sync_window(conn)
    if current_sync and previous_sync:
        freshness = (
            "t.last_seen=? AND julianday(t.first_seen)>julianday(?) "
            "AND julianday(t.first_seen)<=julianday(?)"
        )
        freshness_params = [current_sync, previous_sync, current_sync]
    elif current_sync:
        freshness = "t.last_seen=? AND t.first_seen=?"
        freshness_params = [current_sync, current_sync]
    else:
        freshness = "datetime(t.first_seen) >= datetime('now','-2 minutes')"
        freshness_params = []

    rows = conn.execute(
        f"""SELECT t.*, d.score AS account_score, d.decision AS account_decision
           FROM tenders t
           JOIN (
               SELECT od.source, od.external_id, MAX(od.id) AS max_id
               FROM opportunity_decisions od
               WHERE od.account_id=?
               GROUP BY od.source, od.external_id
           ) latest
             ON latest.source=t.source AND latest.external_id=t.external_id
           JOIN opportunity_decisions d ON d.id=latest.max_id
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE t.first_seen IS NOT NULL
             AND {freshness}
             AND d.decision='QUALIFIED'
             AND d.score >= ?
             AND {actionable_predicate('lc', 't')}
           ORDER BY d.score DESC, datetime(t.first_seen) ASC""",
        (account_id, *freshness_params, min_score),
    ).fetchall()
    events = []
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        d = dict(row)
        event_key = event_key_for(account_id, d)
        score = d.get("account_score", 0)
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account_id, event_key, d.get("id"), d.get("source"), "new_high_match", score, now),
        )
        if cur.rowcount:
            events.append({
                "event_key": event_key,
                "account_id": account_id,
                "tender_id": d.get("id"),
                "source": d.get("source"),
                "score": score,
                "title": d.get("title"),
                "country": d.get("country"),
                "url": d.get("url"),
            })
    conn.commit()
    return events
