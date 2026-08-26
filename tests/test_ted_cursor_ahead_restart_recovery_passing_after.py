"""Passing-after composition for #486 TED cursor-ahead restart recovery.

Exact parent is Persistence #238. This test preserves the original recovery
invariant while adapting the observation point to the repaired staged protocol:
fetch alone must not make a durable cursor authoritative before canonical rows
are persisted.
"""
import sqlite3

import preload
from source_health import get_source_cursor


def _db_factory(path):
    def open_db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return open_db


def test_ted_fetch_does_not_advance_cursor_before_persistence(monkeypatch, tmp_path):
    db_path = tmp_path / "ted-restart.sqlite"
    monkeypatch.setattr(preload._app, "db", _db_factory(db_path))

    fetched = [
        {"publication-date": "2026-08-20", "publication-number": "older-in-batch"},
        {"publication-date": "2026-08-25", "publication-number": "cursor-max"},
    ]
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: list(fetched))
    monkeypatch.setattr(
        preload._app,
        "normalize_ted",
        lambda row: {
            "source": "TED",
            "external_id": row["publication-number"],
            "publication_date": row["publication-date"],
        },
    )

    returned = preload._fetch_ted_with_health()
    assert returned == fetched

    # Model process death immediately after fetch, before legacy/canonical
    # persistence and commit_staged_source_syncs(). The repaired protocol must
    # leave the durable TED cursor unchanged/absent, so restart discovery cannot
    # skip any row merely because fetch completed.
    conn = preload._app.db()
    try:
        assert get_source_cursor(conn, "TED") is None
    finally:
        conn.close()

    # Preserve the original #486 multi-day shape: this proof must not depend on
    # a one-day overlap being wide enough for the fetched batch.
    assert min(row["publication-date"] for row in fetched) == "2026-08-20"
    assert max(row["publication-date"] for row in fetched) == "2026-08-25"
