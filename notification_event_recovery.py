"""Durable reconciliation for missing high-match notification events.

The legacy Notification owner discovers event work only while ``t.first_seen`` is
inside a two-minute wall-clock window. A process can therefore die after the
opportunity and account decision commit but before ``opportunity_events`` is
created; after restart the still-required work can become permanently invisible.

This compatibility boundary makes post-activation event work durable without
creating a second event store and without converting old historical decisions
or stale decision authority into customer notification work.
"""
from __future__ import annotations

import re

import notification_events as _events
from decision_log import current_profile_fingerprint, ensure_decision_table
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from opportunity_match_pipeline import RULE_VERSION

BASELINE_EVENT_TYPE = "notification_reconciliation_baseline"
_BASELINE_KEY = "notification-reconciliation-baseline"
_BASELINE_ID_RE = re.compile(r":notification-reconciliation-baseline:(\d+)$")
_INSTALLED = False


def _baseline_event_key(account_id, decision_id):
    return f"{account_id}:system:{_BASELINE_KEY}:{int(decision_id)}"


def _parse_baseline_id(event_key):
    match = _BASELINE_ID_RE.search(str(event_key or ""))
    return int(match.group(1)) if match else None


def _ensure_decision_parentage(conn):
    """Add exact causal decision identity to durable opportunity events.

    Historical events remain NULL/UNKNOWN. Only newly created recovery events are
    bound to the exact current decision row that authorized their creation.
    """
    _events.ensure_event_table(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_events)")}
    if "decision_id" not in columns:
        conn.execute("ALTER TABLE opportunity_events ADD COLUMN decision_id INTEGER")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_events_decision_parent "
        "ON opportunity_events(account_id,decision_id)"
    )


def reconciliation_baseline_id(conn, account_id):
    """Return the immutable activation decision id for one account, if present."""
    _ensure_decision_parentage(conn)
    row = conn.execute(
        """SELECT event_key FROM opportunity_events
           WHERE account_id=? AND event_type=?
           ORDER BY id ASC LIMIT 1""",
        (str(account_id), BASELINE_EVENT_TYPE),
    ).fetchone()
    if row is None:
        return None
    return _parse_baseline_id(row["event_key"])


def initialize_reconciliation_baseline(conn, account_id, *, existing_account=True):
    """Persist one activation boundary without inventing a second queue/store.

    Existing accounts baseline at their current maximum decision id so installing
    the repair does not backfill historical notification work. A genuinely new
    account baselines at zero so its first decisions are eligible immediately.
    The baseline is immutable across process restarts.
    """
    account_id = str(account_id or "default")
    _ensure_decision_parentage(conn)
    ensure_decision_table(conn)
    current = reconciliation_baseline_id(conn, account_id)
    if current is not None:
        return current

    if existing_account:
        row = conn.execute(
            "SELECT COALESCE(MAX(id),0) AS max_id FROM opportunity_decisions WHERE account_id=?",
            (account_id,),
        ).fetchone()
        baseline = int(row["max_id"] if row else 0)
    else:
        baseline = 0

    conn.execute(
        """INSERT OR IGNORE INTO opportunity_events
           (account_id,event_key,tender_id,source,event_type,score,created_at,decision_id)
           VALUES (?,?,NULL,'SYSTEM',?,0,?,NULL)""",
        (
            account_id,
            _baseline_event_key(account_id, baseline),
            BASELINE_EVENT_TYPE,
            _events._iso_now(),
        ),
    )
    conn.commit()
    stored = reconciliation_baseline_id(conn, account_id)
    if stored is None:
        raise RuntimeError("notification_reconciliation_baseline_invalid")
    return stored


def initialize_existing_account_baselines(conn, account_ids):
    """Baseline all known pre-existing accounts before the worker can create decisions."""
    initialized = {}
    for account_id in account_ids or []:
        account_id = str(account_id or "default")
        initialized[account_id] = initialize_reconciliation_baseline(
            conn, account_id, existing_account=True
        )
    return initialized


def record_new_opportunities(conn, account_id="default", min_score=75):
    """Record every still-missing eligible post-activation event exactly once.

    Elapsed time and incidental source replay cannot acknowledge missing work.
    Eligibility is fail-closed against Decision Intelligence current authority:
    the latest account-scoped decision must meet the Notification threshold,
    current rule semantics and the tenant's current profile fingerprint, while
    the opportunity remains actionable. A stale latest row is never replaced by
    searching backward for older authority.

    The exact decision row that authorizes a new event is persisted as
    ``decision_id``. Later same-score/same-opportunity decisions therefore cannot
    rewrite or make the event's causal parent ambiguous.
    """
    account_id = str(account_id or "default")
    _ensure_decision_parentage(conn)
    ensure_decision_table(conn)
    ensure_lifecycle_table(conn)

    baseline = reconciliation_baseline_id(conn, account_id)
    if baseline is None:
        # Existing accounts are initialized at process startup. Absence here
        # therefore means a genuinely new account created after startup; start
        # from zero so its first decision is never silently skipped.
        baseline = initialize_reconciliation_baseline(
            conn, account_id, existing_account=False
        )

    profile_fp = current_profile_fingerprint(conn, account_id)
    if profile_fp is None:
        # Malformed/unknown profile authority cannot authorize new customer work.
        rows = []
    else:
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
               WHERE d.id > ?
                 AND d.score >= ?
                 AND d.rule_version=?
                 AND d.profile_fingerprint=?
                 AND {actionable_predicate('lc', 't')}
                 AND NOT EXISTS (
                     SELECT 1 FROM opportunity_events e
                     WHERE e.account_id=?
                       AND e.tender_id=t.id
                       AND e.event_type='new_high_match'
                 )
               ORDER BY d.id ASC, t.id ASC""",
            (account_id, baseline, min_score, RULE_VERSION, profile_fp, account_id),
        ).fetchall()

    events = []
    now = _events._iso_now()
    for row in rows:
        item = dict(row)
        event_key = f"{account_id}:{_events._key(item)}"
        decision_id = item.get("account_decision_id")
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at,decision_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                account_id,
                event_key,
                item.get("id"),
                item.get("source"),
                "new_high_match",
                item.get("account_score", 0),
                now,
                decision_id,
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
                    "decision_id": decision_id,
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
    """Install only the worker discovery seam; keep canonical stores/owners intact."""
    global _INSTALLED
    preload_module.record_new_opportunities = record_new_opportunities
    _INSTALLED = True
    return True
