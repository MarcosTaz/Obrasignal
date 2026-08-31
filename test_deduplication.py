"""Tests for the real notification-event deduplication implementation."""
import sqlite3

from decision_log import record_decision
from notification_events import _key, ensure_event_table, record_new_opportunities


def test_same_source_and_external_id_have_same_event_key():
    row = {"source": "TED", "external_id": "2026/S-123456"}
    assert _key(row) == _key(dict(row))


def test_different_external_ids_have_distinct_event_keys():
    a = {"source": "TED", "external_id": "2026/S-123456"}
    b = {"source": "TED", "external_id": "2026/S-654321"}
    assert _key(a) != _key(b)


def test_recording_same_personalized_opportunity_twice_creates_one_event():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tenders (id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT, buyer TEXT, deadline TEXT, country TEXT, first_seen TEXT, score INTEGER, url TEXT)")
    conn.execute("INSERT INTO tenders VALUES (1,'TED','2026/S-123456','Estrutura metálica','Município','2026-09-30','ES',datetime('now'),90,'https://example.test/1')")
    ensure_event_table(conn)
    record_decision(
        conn, 'TED', '2026/S-123456', 'QUALIFIED', 'tenant-specific high match',
        score=90, account_id='default',
    )
    first = record_new_opportunities(conn, min_score=75)
    second = record_new_opportunities(conn, min_score=75)
    assert len(first) == 1
    assert first[0]['score'] == 90
    assert len(second) == 0
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0] == 1
    conn.close()
