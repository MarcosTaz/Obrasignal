"""First-value bootstrap for newly configured accounts.

A new account should not have to wait for the next source poll before the
Radar can show matches. This module performs a bounded, account-scoped
classification pass over recent/open tenders after the company profile is
saved.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app import db
from decision_log import ensure_decision_table
from funnel_integration import persist_and_classify


MAX_BOOTSTRAP_ROWS = 250


def bootstrap_account(account_id: str, limit: int = MAX_BOOTSTRAP_ROWS) -> int:
    """Classify recent/open tenders for one account and return rows evaluated."""
    account_id = str(account_id or "").strip()
    if not account_id:
        return 0

    conn = db()
    try:
        ensure_decision_table(conn)
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
            item = dict(row)
            persist_and_classify(conn, item, False, account_id=account_id)
            evaluated += 1
        conn.commit()
        return evaluated
    finally:
        conn.close()
