"""Account-scoped opportunity eventing for ObraSignal."""
from datetime import datetime, timezone
import hashlib
import re

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
    # Alert feeds and morning digests are tenant-first reads. Without this index,
    # every extra customer grows the scan required for one customer's inbox.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_events_account_feed "
        "ON opportunity_events(account_id, event_type, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_events_account_delivery "
        "ON opportunity_events(account_id, event_type, delivered_at, created_at DESC)"
    )
    conn.commit()


def _latest_sync_finished_at(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_runs'").fetchone()
    if not exists:
        return None
    row = conn.execute("SELECT finished_at FROM sync_runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record qualified actionable opportunities newly discovered by the latest sync.

    ``tenders.score`` is legacy/global presentation state and must never decide
    whether a specific customer receives an alert. The latest account-scoped
    decision is the only scoring authority. In production, newness is tied to
    the exact latest ``sync_runs.finished_at`` value used as ``tenders.first_seen``;
    the short datetime window remains only a compatibility fallback for isolated
    callers/tests without sync-run state.
    """
    account_id = str(account_id or "default")
    ensure_event_table(conn)
    ensure_lifecycle_table(conn)
    sync_finished_at = _latest_sync_finished_at(conn)
    if sync_finished_at:
        freshness = "t.first_seen=?"
        freshness_params = [sync_finished_at]
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
