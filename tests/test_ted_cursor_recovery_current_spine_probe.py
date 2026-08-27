"""Current-spine recovery proof for TED cursor/data ordering."""
import sqlite3

import preload
from source_health import ensure_source_health, get_source_cursor
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs


def _db_factory(path):
    def open_db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        ensure_source_health(conn)
        return conn
    return open_db


def test_ted_fetch_does_not_make_cursor_durable_before_source_side_commit(monkeypatch, tmp_path):
    db_path = tmp_path / "ted-current-spine.sqlite"
    monkeypatch.setattr(preload._app, "db", _db_factory(db_path))
    discard_staged_source_syncs()

    fetched = [
        {"publication-date": "2026-08-20", "publication-number": "older-in-batch"},
        {"publication-date": "2026-08-25", "publication-number": "cursor-max"},
    ]
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: list(fetched))
    monkeypatch.setattr(preload._app, "normalize_ted", lambda row: {
        "source": "TED",
        "external_id": row["publication-number"],
        "signal_type": "TENDER",
        "title": row["publication-number"],
        "source_updated_at": row["publication-date"] + "T00:00:00Z",
    })

    assert preload._fetch_ted_with_health() == fetched

    conn = _db_factory(db_path)()
    try:
        # Process death at this exact point must not strand fetched rows behind a
        # durable watermark. The cursor is staged, not committed by fetch health.
        assert get_source_cursor(conn, "TED") is None
        result = commit_staged_source_syncs(conn)
        assert result["cursors"] == 1
        assert get_source_cursor(conn, "TED") == "20260825"
    finally:
        conn.close()
