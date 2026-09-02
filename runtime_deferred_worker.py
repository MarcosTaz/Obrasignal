"""Defer heavy source ingestion until customer HTTP capacity is stable.

Render/Gunicorn may begin routing traffic as soon as one worker reports the exact
build. Starting the procurement refresh at the same instant can consume CPU and
SQLite capacity during the most sensitive readiness window. The elected runtime
leader therefore waits a short bounded grace period before starting the existing
source worker. The worker itself and its polling cadence remain unchanged.

Production also repairs active accounts whose persisted public corpus has not
produced any visible relevant decision yet. This closes both the new-account gap
and the migration gap after a ranking fix: customers must not remain stuck with a
small stale bootstrap forever merely because they technically have decision rows.
"""
from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

# Ten seconds is enough to let Gunicorn expose its health/readiness path while
# preventing routine UI deploys from postponing procurement ingestion for minutes.
DEFAULT_SOURCE_START_DELAY_SECONDS = 10
MAX_SOURCE_START_DELAY_SECONDS = 600


def source_start_delay_seconds() -> int:
    raw = (os.getenv("OBRASIGNAL_SOURCE_START_DELAY_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_SOURCE_START_DELAY_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_SOURCE_START_DELAY_SECONDS
    return max(0, min(MAX_SOURCE_START_DELAY_SECONDS, value))


def _repair_accounts_from_existing_corpus() -> int:
    """Populate a bounded first-value radar for accounts with no visible match.

    The shared procurement corpus contains public tender data only. Account
    scoring remains tenant-scoped. A repair is needed when an active account has
    no decisions at all *or* has decisions but none at the customer-visible
    60-point relevance boundary. Re-running the bounded bootstrap also migrates
    old decisions after matcher improvements without touching another tenant.
    """
    from app import db
    from account_registry import list_active_accounts
    from account_onboarding import bootstrap_account

    conn = db()
    try:
        if not conn.execute("SELECT 1 FROM tenders LIMIT 1").fetchone():
            return 0
        account_ids = list_active_accounts(conn)
        needs_repair = []
        for raw_account_id in account_ids:
            account_id = str(raw_account_id or "").strip()
            if not account_id:
                continue
            has_decisions = conn.execute(
                "SELECT 1 FROM opportunity_decisions WHERE account_id=? LIMIT 1",
                (account_id,),
            ).fetchone()
            has_visible_relevance = conn.execute(
                "SELECT 1 FROM opportunity_decisions WHERE account_id=? AND score>=60 LIMIT 1",
                (account_id,),
            ).fetchone()
            if not has_decisions or not has_visible_relevance:
                needs_repair.append(account_id)
    finally:
        conn.close()

    repaired = 0
    for account_id in needs_repair:
        try:
            repaired += int(bootstrap_account(account_id) or 0)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            print(f"account first-value repair error ({account_id}):", exc)
    if needs_repair:
        print(f"account first-value repair: accounts={len(needs_repair)} classified={repaired}")
    return repaired


def _run_after_delay(
    start_worker: Callable[[], object],
    delay_seconds: int,
    sleep_func: Callable[[float], object],
    repair_existing: bool = False,
) -> None:
    if delay_seconds:
        sleep_func(delay_seconds)
    if repair_existing:
        try:
            _repair_accounts_from_existing_corpus()
        except Exception as exc:  # pragma: no cover - defensive process boundary
            print("account first-value repair boundary error:", exc)
    try:
        start_worker()
    except Exception as exc:  # pragma: no cover - defensive process boundary
        print("source worker deferred start error:", exc)


def start_source_worker_after_readiness(
    start_worker: Callable[[], object],
    *,
    delay_seconds: int | None = None,
    sleep_func: Callable[[float], object] = time.sleep,
    thread_factory=threading.Thread,
):
    """Start the source worker asynchronously after a bounded readiness grace.

    This function never blocks WSGI import/readiness. It returns the thread so
    tests and diagnostics can observe the launch contract without changing the
    underlying worker implementation. The production/default path performs the
    account first-value repair immediately before starting ingestion; explicit
    delays used by unit tests preserve the original isolated timing contract.
    """
    production_default = delay_seconds is None
    delay = source_start_delay_seconds() if production_default else max(0, min(MAX_SOURCE_START_DELAY_SECONDS, int(delay_seconds)))
    thread = thread_factory(
        target=_run_after_delay,
        args=(start_worker, delay, sleep_func, production_default),
        name="obrasignal-deferred-source-worker",
        daemon=True,
    )
    thread.start()
    return thread
