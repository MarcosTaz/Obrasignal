"""Defer heavy source ingestion until customer HTTP capacity is stable.

Render/Gunicorn may begin routing traffic as soon as one worker reports the exact
build. Starting the procurement refresh at the same instant can consume CPU and
SQLite capacity during the most sensitive readiness window. The elected runtime
leader therefore waits a bounded grace period before starting the existing
source worker. The worker itself and its polling cadence remain unchanged.
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


def _run_after_delay(start_worker: Callable[[], object], delay_seconds: int, sleep_func: Callable[[float], object]) -> None:
    if delay_seconds:
        sleep_func(delay_seconds)
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
    underlying worker implementation.
    """
    delay = source_start_delay_seconds() if delay_seconds is None else max(0, min(MAX_SOURCE_START_DELAY_SECONDS, int(delay_seconds)))
    thread = thread_factory(
        target=_run_after_delay,
        args=(start_worker, delay, sleep_func),
        name="obrasignal-deferred-source-worker",
        daemon=True,
    )
    thread.start()
    return thread
