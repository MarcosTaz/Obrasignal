"""First-value bootstrap for newly configured accounts.

A new account should not have to wait for the next source poll before the
Radar can show matches. This module performs a bounded, account-scoped
classification pass over recent/open tenders after the company profile is
saved and emits high-match events for the same account.
"""
from __future__ import annotations

from app import db
from decision_log import ensure_decision_table
from funnel_integration import persist_and_classify
from notification_events import ensure_event_table

MAX_BOOTSTRAP_ROWS = 250


def _emit_bootstrap_events(conn, account_id: str) -> int:
    ensure_event_table(conn)
    rows = conn.execute(
        """SELECT t.*, d.score AS account_score
           FROM tenders t
           JOIN (
               SELECT od.source, od.external_id, MAX(od.id) AS max_id
               FROM opportunity_decisions od
               WHERE od.account_id=?
               GROUP BY od.source, od.external_id
           ) latest ON latest.source=t.source AND latest.external_id=t.external_id
           JOIN opportunity_decisions d ON d.id=latest.max_id
           WHERE d.score >= 75
             AND (t.deadline IS NULL OR t.deadline='' OR datetime(t.deadline) >= datetime('now'))
           ORDER BY d.score DESC, COALESCE(t.publication_date, t.first_seen) DESC
           LIMIT ?""",
        (account_id, MAX_BOOTSTRAP_ROWS),
    ).fetchall()
    created = 0
    for row in rows:
        item = dict(row)
        event_key = f"{account_id}:{item.get('source','')}:{item.get('external_id','')}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (account_id, event_key, item.get('id'), item.get('source'), 'new_high_match', item.get('account_score', 0)),
        )
        created += int(cur.rowcount or 0)
    conn.commit()
    return created


def bootstrap_account(account_id: str, limit: int = MAX_BOOTSTRAP_ROWS) -> int:
    """Classify recent/open tenders for one account and emit initial alerts."""
    account_id = str(account_id or "").strip()
    if not account_id:
        return 0
    conn = db()
    try:
        ensure_decision_table(conn)
        ensure_event_table(conn)
        rows = conn.execute(
            """SELECT t.*
               FROM tenders t
               WHERE t.deadline IS NULL
                  OR t.deadline=''
                  OR datetime(t.deadline) >= datetime('now')
               ORDER BY COALESCE(t.publication_date, t.first_seen) DESC
               LIMIT ?""",
            (max(1, min(int(limit), MAX_BOOTSTRAP_ROWS)),),
        ).fetchall()
        evaluated = 0
        for row in rows:
            persist_and_classify(conn, dict(row), False, account_id=account_id)
            evaluated += 1
        _emit_bootstrap_events(conn, account_id)
        return evaluated
    finally:
        conn.close()
