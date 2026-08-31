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
BOOTSTRAP_COMMIT_BATCH = 25


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

    Candidate selection prefers the account's configured countries. Expensive
    scoring is completed before the first decision INSERT, then decisions are
    persisted in short batches so customer profile saves do not hold SQLite's
    single writer lock while classification is still computing.
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
        params.append(max(1, min(int(limit), MAX_BOOTSTRAP_ROWS)))
        rows = conn.execute(
            f"""SELECT t.*
               FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE {' AND '.join(where)}
               ORDER BY COALESCE(t.score,0) DESC,
                        COALESCE(NULLIF(t.publication_date,''), t.first_seen) DESC
               LIMIT ?""",
            params,
        ).fetchall()

        prepared = []
        for row in rows:
            item = dict(row)
            prepared.append((item, evaluate_row(item, profile=profile)))

        for index, (item, evaluation) in enumerate(prepared, start=1):
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
        if prepared and len(prepared) % BOOTSTRAP_COMMIT_BATCH:
            conn.commit()

        _emit_bootstrap_events(conn, account_id)
        return len(prepared)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
