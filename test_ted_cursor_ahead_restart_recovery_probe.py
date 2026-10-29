"""Execution Factory failing-before for TED cursor-ahead-of-data recovery.

DO NOT MERGE / NOT SOURCE OWNER REPAIR / NOT CANONICAL.
"""
import sqlite3

import preload


def _db_factory(path):
    def open_db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return open_db


def test_ted_one_day_overlap_covers_every_row_from_cursor_committed_batch(monkeypatch, tmp_path):
    """Crash after cursor commit must not strand rows from the fetched batch."""
    db_path = tmp_path / "ted-restart.sqlite"
    monkeypatch.setattr(preload._app, "db", _db_factory(db_path))

    # One successful TED response can contain notices spanning more than one
    # publication day. _fetch_ted_with_health commits the maximum date cursor
    # before the later tender-persistence path runs.
    fetched = [
        {"publication-date": "2026-08-20", "publication-number": "older-in-batch"},
        {"publication-date": "2026-08-25", "publication-number": "cursor-max"},
    ]
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: list(fetched))

    returned = preload._fetch_ted_with_health()
    assert returned == fetched

    # Model process death here: no tender rows are persisted. On restart the
    # normal discovery lower bound is derived from the already-durable cursor.
    next_since = preload._ted_since_date()
    oldest_fetched = min(row["publication-date"].replace("-", "") for row in fetched)

    # Required recovery invariant: every fetched-but-unpersisted row remains in
    # the next discovery range. Current one-day overlap is expected to fail this
    # when a batch spans more than one day.
    assert oldest_fetched >= next_since
