"""First-value bootstrap for newly configured accounts.

A new account should not have to wait for the next source poll before the
Radar can show matches. This module performs a bounded, account-scoped
classification pass over recent/open tenders after the company profile is
saved and emits high-match events for the same account.
"""
from __future__ import annotations

from app import APP, db
from decision_log import current_profile_fingerprint, latest_current_decision
from funnel_integration import persist_and_classify
from opportunity_lifecycle import ensure_lifecycle_table
from opportunity_match_pipeline import RULE_VERSION

MAX_BOOTSTRAP_ROWS = 250


def _emit_bootstrap_events(conn, account_id: str) -> int:
    ensure_lifecycle_table(conn)
    profile_fingerprint = current_profile_fingerprint(conn, account_id)
    if profile_fingerprint is None:
        # Malformed/unknown profile authority cannot create positive customer work.
        return 0
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
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE d.score >= 75
             AND d.rule_version=?
             AND d.profile_fingerprint=?
             AND COALESCE(lc.is_actionable,1)=1
             AND (t.deadline IS NULL OR t.deadline='' OR datetime(t.deadline) >= datetime('now'))
           ORDER BY d.score DESC, COALESCE(t.publication_date, t.first_seen) DESC
           LIMIT ?""",
        (account_id, RULE_VERSION, profile_fingerprint, MAX_BOOTSTRAP_ROWS),
    ).fetchall()
    created = 0
    for row in rows:
        item = dict(row)
        # SQL already gates score/rule/profile. The canonical opportunity
        # revision is content-addressed in Python; require the reusable full
        # current-authority contract before this decision can create work.
        if latest_current_decision(
            conn,
            item.get("source"),
            item.get("external_id"),
            account_id=account_id,
            expected_rule_version=RULE_VERSION,
        ) is None:
            continue
        event_key = f"{account_id}:{item.get('source','')}:{item.get('external_id','')}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (account_id, event_key, item.get('id'), item.get('source'), 'new_high_match', item.get('account_score', 0)),
        )
        created += int(cur.rowcount or 0)
    conn.commit()

    # Bootstrap-created opportunity_events are the same canonical notification
    # truth as source-sync events. Dispatch through the same best-effort sender
    # so first-value events do not wait for an unrelated later ingestion pass.
    try:
        from notification_events import submit_pending_pushes
        submit_pending_pushes(conn, account_id)
    except Exception as exc:
        # Profile/Radar bootstrap must stay available if notification transport
        # or its bounded dispatch path is unavailable. Log only the error class;
        # no tenant or opportunity content is emitted.
        APP.logger.warning("bootstrap push dispatch failed: %s", type(exc).__name__)
    return created


def bootstrap_account(account_id: str, limit: int = MAX_BOOTSTRAP_ROWS) -> int:
    """Classify recent/open, currently actionable tenders for one account."""
    account_id = str(account_id or "").strip()
    if not account_id:
        return 0
    conn = db()
    try:
        ensure_lifecycle_table(conn)
        rows = conn.execute(
            """SELECT t.*
               FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE COALESCE(lc.is_actionable,1)=1
                 AND (t.deadline IS NULL
                      OR t.deadline=''
                      OR datetime(t.deadline) >= datetime('now'))
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
