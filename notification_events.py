"""Account-scoped opportunity eventing for ObraSignal."""
from datetime import datetime, timezone
import hashlib
import re


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


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record high-value opportunities for exactly one account."""
    ensure_event_table(conn)
    account_id = str(account_id or "default")
    rows = conn.execute(
        """SELECT * FROM tenders
           WHERE first_seen IS NOT NULL
             AND first_seen >= datetime('now','-2 minutes')
             AND score >= ?
           ORDER BY score DESC, first_seen ASC""",
        (min_score,),
    ).fetchall()
    events = []
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        d = dict(row)
        base_key = _key(d)
        event_key = f"{account_id}:{base_key}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (account_id, event_key, d.get("id"), d.get("source"), "new_high_match", d.get("score", 0), now),
        )
        if cur.rowcount:
            events.append({
                "event_key": event_key,
                "account_id": account_id,
                "tender_id": d.get("id"),
                "source": d.get("source"),
                "score": d.get("score", 0),
                "title": d.get("title"),
                "country": d.get("country"),
                "url": d.get("url"),
            })
    conn.commit()
    return events
