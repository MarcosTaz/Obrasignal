"""Defer heavy source ingestion until customer HTTP capacity is stable.

Render/Gunicorn may begin routing traffic as soon as one worker reports the exact
build. Starting the procurement refresh at the same instant can consume CPU and
SQLite capacity during the most sensitive readiness window. The elected runtime
leader therefore waits a bounded grace period before starting the existing
source worker. The worker itself and its polling cadence remain unchanged.

Production also repairs active accounts that have no decision rows yet when a
persisted tender corpus already exists. This closes the first-value gap where an
account can be created between source polls (or while a deploy repeatedly resets
the source-worker grace period) and otherwise see a permanently empty Radar.
"""
from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

DEFAULT_SOURCE_START_DELAY_SECONDS = 120
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
    """Populate a bounded first-value radar for active accounts missing decisions.

    This runs only in the elected background leader and never on a customer
    request. Tenant scoring remains account-scoped; the shared procurement
    corpus contains public tender data only. Accounts that already have any
    decision rows are left untouched and normal incremental refresh remains the
    authoritative convergence path.
    """
    from app import db
    from account_registry import list_active_accounts
    from account_onboarding import bootstrap_account

    conn = db()
    try:
        if not conn.execute("SELECT 1 FROM tenders LIMIT 1").fetchone():
            return 0
        account_ids = list_active_accounts(conn)
        missing = [
            str(account_id)
            for account_id in account_ids
            if not conn.execute(
                "SELECT 1 FROM opportunity_decisions WHERE account_id=? LIMIT 1",
                (str(account_id),),
            ).fetchone()
        ]
    finally:
        conn.close()

    repaired = 0
    for account_id in missing:
        try:
            repaired += int(bootstrap_account(account_id) or 0)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            print(f"account first-value repair error ({account_id}):", exc)
    if missing:
        print(f"account first-value repair: accounts={len(missing)} classified={repaired}")
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
