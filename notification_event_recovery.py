"""Durable reconciliation for missing high-match notification events.

The legacy Notification owner discovers event work only while ``t.first_seen`` is
inside a two-minute wall-clock window. A process can therefore die after the
opportunity and account decision commit but before ``opportunity_events`` is
created; after restart the still-required work can become permanently invisible.

This owner-side compatibility boundary replaces the worker's discovery function
with a durable post-cutover anti-join. It deliberately does not rewrite the
canonical opportunity/decision owners and does not turn old historical rows into
a notification backlog.
"""
from __future__ import annotations

import notification_events as _events
from decision_log import ensure_decision_table
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table

# Migration epoch, not a sliding freshness window. Decisions created at/after
# this owner-candidate cutover remain rediscoverable indefinitely until their
# canonical event exists. Older decisions are intentionally not backfilled into
# the notification channel merely because this repair is installed later.
DURABLE_EVENT_RECONCILIATION_EPOCH = "2026-08-26T23:00:00+00:00"
_INSTALLED = False


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record every still-missing eligible post-cutover event exactly once.

    Eligibility remains the Notification owner's existing contract: latest
    account-scoped decision score at/above ``min_score`` plus current effective
    actionability. The only changed dimension is discovery durability: elapsed
    wall-clock time or incidental source replay can no longer acknowledge work.
    """
    account_id = str(account_id or "default")
    _events.ensure_event_table(conn)
    ensure_decision_table(conn)
    ensure_lifecycle_table(conn)

    rows = conn.execute(
        f"""SELECT t.*, d.id AS account_decision_id,
                   d.score AS account_score, d.decided_at AS account_decided_at
           FROM tenders t
           JOIN (
               SELECT source, external_id, MAX(id) AS max_id
               FROM opportunity_decisions
               WHERE account_id=?
               GROUP BY source, external_id
           ) latest ON latest.source=t.source AND latest.external_id=t.external_id
           JOIN opportunity_decisions d ON d.id=latest.max_id
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE d.score >= ?
             AND datetime(d.decided_at) >= datetime(?)
             AND {actionable_predicate('lc', 't')}
             AND NOT EXISTS (
                 SELECT 1 FROM opportunity_events e
                 WHERE e.account_id=?
                   AND e.tender_id=t.id
                   AND e.event_type='new_high_match'
             )
           ORDER BY d.id ASC, t.id ASC""",
        (account_id, min_score, DURABLE_EVENT_RECONCILIATION_EPOCH, account_id),
    ).fetchall()

    events = []
    now = _events._iso_now()
    for row in rows:
        item = dict(row)
        event_key = f"{account_id}:{_events._key(item)}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                account_id,
                event_key,
                item.get("id"),
                item.get("source"),
                "new_high_match",
                item.get("account_score", 0),
                now,
            ),
        )
        if cur.rowcount:
            events.append(
                {
                    "event_key": event_key,
                    "account_id": account_id,
                    "tender_id": item.get("id"),
                    "source": item.get("source"),
                    "score": item.get("account_score", 0),
                    "title": item.get("title"),
                    "country": item.get("country"),
                    "url": item.get("url"),
                }
            )
    conn.commit()

    # Preserve owner delivery semantics. The dispatch guard, when installed,
    # remains the dynamic notification_events.submit_pending_pushes authority.
    try:
        _events.reconcile_push_receipts(conn, account_id)
    except Exception as exc:
        _events.APP.logger.warning(
            "push receipt reconciliation failed: %s", type(exc).__name__
        )
    _events.submit_pending_pushes(conn, account_id)
    return events


def install(preload_module):
    """Install only the worker discovery seam; keep all owner stores canonical."""
    global _INSTALLED
    current = getattr(preload_module, "record_new_opportunities", None)
    if current is record_new_opportunities:
        _INSTALLED = True
        return False
    preload_module.record_new_opportunities = record_new_opportunities
    _INSTALLED = True
    return True
