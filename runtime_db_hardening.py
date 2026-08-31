"""Production SQLite hardening for customer traffic beside background ingestion.

The product intentionally runs one Render instance with a persistent SQLite
file. Reads should remain available while ingestion writes, and account
classification should not churn hundreds of redundant commits every minute.
"""
from __future__ import annotations

DECISION_COMMIT_BATCH = 25


def _enable_wal(app_module) -> str:
    """Enable SQLite WAL once at startup; the journal mode persists in the DB."""
    conn = app_module.db()
    try:
        row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        mode = str(row[0] if row else "").lower()
        if mode != "wal":
            raise RuntimeError(f"sqlite_wal_not_enabled:{mode or 'unknown'}")
        conn.commit()
        return mode
    finally:
        conn.close()


def _optimized_account_decision_recorder(preload_module):
    from account_registry import list_active_accounts
    from auth_context import configured_identity
    from company_profile import load_profile
    from decision_log import ensure_decision_table
    from funnel_integration import persist_and_classify
    from opportunity_match_pipeline import RULE_VERSION, evaluate_row

    def record_account_decisions(conn):
        """Persist changed account decisions in short write-only batches.

        Expensive scoring and comparison happen before the first INSERT for each
        account. This prevents SQLite's single writer lock from being held while
        the next opportunities are still being evaluated.
        """
        run = conn.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not run or not run["finished_at"]:
            return 0
        rows = conn.execute("SELECT * FROM tenders WHERE last_seen=?", (run["finished_at"],)).fetchall()
        accounts = list_active_accounts(conn) or [configured_identity().account_id]
        ensure_decision_table(conn)

        recorded = 0
        for account_id in accounts:
            profile = load_profile(account_id)
            changes = []
            for row in rows:
                item = dict(row)
                source = item.get("source", "")
                external_id = item.get("external_id", "")
                evaluation = evaluate_row(item, profile=profile)
                previous = conn.execute(
                    """SELECT decision,score,reason,rule_version
                       FROM opportunity_decisions
                       WHERE account_id=? AND source=? AND external_id=?
                       ORDER BY id DESC LIMIT 1""",
                    (str(account_id), source, external_id),
                ).fetchone()
                if previous and (
                    previous["decision"] == evaluation["decision"]
                    and previous["score"] == evaluation["profile_score"]
                    and previous["reason"] == evaluation["reason"]
                    and previous["rule_version"] == RULE_VERSION
                ):
                    continue
                changes.append((item, evaluation))

            for index, (item, evaluation) in enumerate(changes, start=1):
                persist_and_classify(
                    conn,
                    item,
                    True,
                    account_id=account_id,
                    profile=profile,
                    evaluation=evaluation,
                    commit=False,
                    ensure_schema=False,
                )
                recorded += 1
                if index % DECISION_COMMIT_BATCH == 0:
                    conn.commit()
            if changes and len(changes) % DECISION_COMMIT_BATCH:
                conn.commit()

        return recorded

    return record_account_decisions


def install(preload_module, app_module) -> dict:
    """Install production-only DB hardening before background workers start."""
    mode = _enable_wal(app_module)
    preload_module._record_account_decisions = _optimized_account_decision_recorder(preload_module)
    return {"journal_mode": mode, "decision_commit_batch": DECISION_COMMIT_BATCH}
