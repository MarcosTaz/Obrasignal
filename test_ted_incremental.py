import sqlite3
from datetime import datetime, timezone

import preload


def test_ted_cursor_advances_only_after_success():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    from source_health import ensure_source_health, get_source_cursor, set_source_cursor
    ensure_source_health(conn)
    assert get_source_cursor(conn, 'TED') is None
    set_source_cursor(conn, 'TED', '20260817')
    assert get_source_cursor(conn, 'TED') == '20260817'
    conn.close()


def test_ted_since_uses_one_day_overlap(monkeypatch):
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    from source_health import ensure_source_health, set_source_cursor
    ensure_source_health(conn)
    set_source_cursor(conn, 'TED', '20260817')

    monkeypatch.setattr(preload._app, 'db', lambda: conn)
    assert preload._ted_since_date() == '20260816'
    conn.close()


def test_max_ted_publication_date_supports_iso_and_compact_dates():
    rows = [
        {'publication-date': '2026-08-17'},
        {'publication-date': '20260818'},
        {'publication-date': None},
    ]
    assert preload._max_ted_publication_date(rows) == '20260818'
