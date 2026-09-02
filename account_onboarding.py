"""First-value bootstrap for newly configured accounts.

A new account should not have to wait for the next source poll before the
Radar can show matches. This module performs a deliberately small,
account-scoped classification pass after the company profile is saved.
The normal ingestion/decision pipeline continues coverage afterwards; profile
writes must never be held hostage by a full-corpus reclassification.
"""
from __future__ import annotations

from app import db
from company_profile import load_profile
from decision_log import ensure_decision_table
from funnel_integration import persist_and_classify
from notification_events import event_key_for
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from opportunity_match_pipeline import evaluate_row

# This runs inside POST /profile. Keep it a first-value sample, not a batch job.
# 250 rows exceeded the real 30 s production contract even after batching.
MAX_BOOTSTRAP_ROWS = 50
MAX_BOOTSTRAP_CANDIDATES = 80
BOOTSTRAP_COMMIT_BATCH = 25

# A customer starts with "Apenas oportunidades abertas" enabled. Therefore the
# bounded first-value sample must prefer tenders whose deadline is explicitly
# still open. Unknown-deadline tenders remain eligible, but they no longer fill
# all bootstrap slots while the customer's initial Radar appears empty.
CONFIRMED_OPEN_SQL = """t.deadline IS NOT NULL AND TRIM(t.deadline)<>'' AND (
    (LENGTH(TRIM(t.deadline))=10 AND date(t.deadline)>=date('now')) OR
    (LENGTH(TRIM(t.deadline))<>10 AND datetime(t.deadline)>=datetime('now'))
)"""

_DECISION_ORDER = {"QUALIFIED": 0, "REVIEW": 1, "REJECT": 2}


def _bootstrap_rank(pair):
    """Put the account's strongest matches ahead of generic source ranking."""
    item, evaluation = pair
    return (
        _DECISION_ORDER.get(str(evaluation.get("decision") or "REJECT"), 3),
        -int(evaluation.get("profile_score") or 0),
        -int(evaluation.get("lot_score") or 0),
        -int(item.get("score") or 0),
        str(item.get("external_id") or item.get("id") or ""),
    )


def _emit_bootstrap_events(conn, account_id: str) -> int:
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT t.*, d.score AS account_score
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
           WHERE d.decision='QUALIFIED'
             AND d.score >= 75
             AND {actionable_predicate('lc', 't')}
           ORDER BY d.score DESC, COALESCE(NULLIF(t.publication_date,''), t.first_seen) DESC
           LIMIT ?""",
        (account_id, MAX_BOOTSTRAP_ROWS),
    ).fetchall()
    created = 0
    for row in rows:
        item = dict(row)
        event_key = event_key_for(account_id, item)
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
    """Classify a bounded first-value sample for one account quickly.

    The database first supplies a small candidate pool biased toward the
    account's countries and confirmed-open work. Crucially, those candidates are
    then evaluated against the *saved company profile* before the final bootstrap
    rows are chosen. This prevents a high generic/source score from consuming all
    50 first-value slots with work that does not match the customer's stated
    activity or specifications.
    """
    account_id = str(account_id or "").strip()
    if not account_id:
        return 0
    conn = db()
    try:
        ensure_lifecycle_table(conn)
        ensure_decision_table(conn)
        profile = load_profile(account_id)
        countries = [str(value).strip().upper() for value in (profile.get("countries") or []) if str(value).strip()]
        where = [actionable_predicate('lc', 't')]
        params = []
        if countries:
            placeholders = ",".join("?" for _ in countries)
            where.append(f"UPPER(COALESCE(t.country,'')) IN ({placeholders})")
            params.extend(countries)

        requested_limit = max(1, min(int(limit), MAX_BOOTSTRAP_ROWS))
        candidate_limit = min(MAX_BOOTSTRAP_CANDIDATES, max(requested_limit, requested_limit * 2))
        params.append(candidate_limit)
        rows = conn.execute(
            f"""SELECT t.*
               FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE {' AND '.join(where)}
               ORDER BY CASE WHEN {CONFIRMED_OPEN_SQL} THEN 0 ELSE 1 END,
                        COALESCE(t.score,0) DESC,
                        COALESCE(NULLIF(t.publication_date,''), t.first_seen) DESC
               LIMIT ?""",
            params,
        ).fetchall()

        prepared = []
        for row in rows:
            item = dict(row)
            prepared.append((item, evaluate_row(item, profile=profile)))

        # Source ordering is only candidate discovery. Final first-value
        # selection is explicitly account-specific.
        prepared.sort(key=_bootstrap_rank)
        selected = prepared[:requested_limit]

        for index, (item, evaluation) in enumerate(selected, start=1):
            persist_and_classify(
                conn,
                item,
                False,
                account_id=account_id,
                profile=profile,
                evaluation=evaluation,
                commit=False,
                ensure=False,
            )
            if index % BOOTSTRAP_COMMIT_BATCH == 0:
                conn.commit()
        if selected and len(selected) % BOOTSTRAP_COMMIT_BATCH:
            conn.commit()

        _emit_bootstrap_events(conn, account_id)
        return len(selected)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
