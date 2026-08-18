"""Near-real-time opportunity eventing for ObraSignal.

This module deliberately separates detection from delivery. A new opportunity
is recorded once, with a stable dedupe key, so push/email delivery can be
attached later without creating duplicate alerts when the same notice is seen
again or arrives from multiple sources.
"""
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
            event_key TEXT NOT NULL UNIQUE,
            tender_id INTEGER,
            source TEXT,
            event_type TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            delivered_at TEXT
        )"""
    )
    conn.commit()


def record_new_opportunities(conn, min_score=75):
    """Record high-value opportunities first seen since the previous sync.

    Returns event dictionaries ready for a future push/email adapter.
    No external notification service is called here, keeping ingestion safe.
    """
    ensure_event_table(conn)
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
        key = _key(d)
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?)""",
            (key, d.get("id"), d.get("source"), "new_high_match", d.get("score", 0), now),
        )
        if cur.rowcount:
            events.append({
                "event_key": key,
                "tender_id": d.get("id"),
                "source": d.get("source"),
                "score": d.get("score", 0),
                "title": d.get("title"),
                "country": d.get("country"),
                "url": d.get("url"),
            })
    conn.commit()
    return events
