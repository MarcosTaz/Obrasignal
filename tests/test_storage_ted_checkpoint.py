import sqlite3

import app
import preload
import source_runtime
from signal_store import get_signal_record
from source_health import get_source_cursor


def _point_db(monkeypatch, tmp_path):
    path = tmp_path / "ted-checkpoint.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    app.init_db()
    return path


def _ted_row(external_id="123-2026", publication_date="2026-08-25"):
    return {
        "publication-number": external_id,
        "publication-date": publication_date,
        "notice-title": "Reliability test tender",
        "buyer-country": "PRT",
    }


def test_ted_fetch_stages_but_does_not_advance_cursor_before_canonical_commit(monkeypatch, tmp_path):
    _point_db(monkeypatch, tmp_path)
    source_runtime.discard_staged_source_syncs()
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: [_ted_row()])

    rows = preload._fetch_ted_with_health()
    assert len(rows) == 1

    conn = app.db()
    try:
        # Fetch success alone is not a persistence checkpoint. The cursor and
        # canonical Signal must remain absent until the source-side transaction.
        assert get_source_cursor(conn, "TED") is None
        assert get_signal_record(conn, "TED", "123-2026") is None

        result = source_runtime.commit_staged_source_syncs(conn)
        assert result["signal_records"] == 1
        assert result["cursors"] == 1
        assert get_source_cursor(conn, "TED") == "20260825"
        assert get_signal_record(conn, "TED", "123-2026") is not None
    finally:
        conn.close()
        source_runtime.discard_staged_source_syncs()


def test_ted_canonical_failure_rolls_back_signal_and_cursor_together(monkeypatch, tmp_path):
    _point_db(monkeypatch, tmp_path)
    source_runtime.discard_staged_source_syncs()
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: [_ted_row()])
    preload._fetch_ted_with_health()

    def fail_metadata(*args, **kwargs):
        raise RuntimeError("synthetic metadata failure")

    monkeypatch.setattr(source_runtime, "persist_source_metadata", fail_metadata)
    conn = app.db()
    try:
        try:
            source_runtime.commit_staged_source_syncs(conn)
        except RuntimeError as exc:
            assert str(exc) == "synthetic metadata failure"
        else:
            raise AssertionError("source-side failure must propagate")

        assert get_source_cursor(conn, "TED") is None
        assert get_signal_record(conn, "TED", "123-2026") is None
    finally:
        conn.close()
        source_runtime.discard_staged_source_syncs()
