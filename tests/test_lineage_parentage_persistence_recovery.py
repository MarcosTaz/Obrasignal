"""Persistence acceptance for exact Notification lineage parentage.

Synthetic SQLite only. This test does not choose owner schema architecture; it
checks the durability properties required before #607 + #617 can be treated as
Persistence-ready rather than merely runtime-green.
"""
from pathlib import Path
import sqlite3

import notification_event_recovery as recovery
import notification_events as events


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _legacy_schema(conn):
    """Create the pre-parentage shapes that owner migrations must preserve."""
    conn.execute(
        """CREATE TABLE opportunity_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL DEFAULT 'default',
            event_key TEXT NOT NULL UNIQUE,
            tender_id INTEGER,
            source TEXT,
            event_type TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            delivered_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE push_deliveries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            push_device_id INTEGER NOT NULL,
            ticket_id TEXT,
            submitted_at TEXT,
            last_error TEXT,
            UNIQUE(event_id,push_device_id)
        )"""
    )
    conn.commit()


def _insert_legacy_rows(conn):
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a','legacy-event',1,'TED','new_high_match',88,
                     '2026-08-27T12:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,last_error
           ) VALUES (1,10,'ticket-unique','2026-08-27T12:01:00+00:00',NULL)"""
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,last_error
           ) VALUES (1,11,'ticket-duplicate','2026-08-27T12:02:00+00:00',NULL)"""
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,last_error
           ) VALUES (1,12,'ticket-duplicate','2026-08-27T12:03:00+00:00',NULL)"""
    )
    conn.commit()


def _migrate(conn):
    recovery._ensure_decision_parentage(conn)
    events.ensure_push_tables(conn)
    conn.commit()


def _snapshot(conn):
    event = conn.execute(
        "SELECT id,account_id,event_key,decision_id FROM opportunity_events WHERE event_key='legacy-event'"
    ).fetchone()
    parents = [
        tuple(row)
        for row in conn.execute(
            "SELECT ticket_id,push_delivery_id FROM push_ticket_parents ORDER BY ticket_id"
        ).fetchall()
    ]
    deliveries = [
        tuple(row)
        for row in conn.execute(
            "SELECT id,event_id,push_device_id,ticket_id FROM push_deliveries ORDER BY id"
        ).fetchall()
    ]
    return tuple(event), tuple(parents), tuple(deliveries)


def test_parentage_migration_is_idempotent_and_does_not_invent_history(tmp_path):
    db = tmp_path / 'lineage.sqlite'
    conn = _connect(db)
    _legacy_schema(conn)
    _insert_legacy_rows(conn)

    _migrate(conn)
    first = _snapshot(conn)
    _migrate(conn)
    second = _snapshot(conn)

    assert second == first
    assert first[0][3] is None

    parents = dict(first[1])
    assert set(parents) == {'ticket-unique'}
    unique_delivery = conn.execute(
        "SELECT id FROM push_deliveries WHERE ticket_id='ticket-unique'"
    ).fetchone()[0]
    assert parents['ticket-unique'] == unique_delivery
    assert conn.execute(
        "SELECT 1 FROM push_ticket_parents WHERE ticket_id='ticket-duplicate'"
    ).fetchone() is None
    conn.close()


def test_corrupt_or_cross_parent_claim_cannot_authorize_receipt_lookup(tmp_path):
    db = tmp_path / 'corrupt.sqlite'
    conn = _connect(db)
    events.ensure_event_table(conn)

    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-a','event-a',1,'TED','new_high_match',90,
                     '2000-01-01T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES ('account-b','event-b',2,'TED','new_high_match',90,
                     '2000-01-01T00:00:00+00:00')"""
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,
               last_attempt_at,expo_push_token
           ) VALUES (1,101,'ticket-a','2000-01-01T00:00:00+00:00',1,
                     '2000-01-01T00:00:00+00:00','ExpoPushToken[a]')"""
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,
               last_attempt_at,expo_push_token
           ) VALUES (2,202,'ticket-b','2000-01-01T00:00:00+00:00',1,
                     '2000-01-01T00:00:00+00:00','ExpoPushToken[b]')"""
    )
    a_id = conn.execute("SELECT id FROM push_deliveries WHERE ticket_id='ticket-a'").fetchone()[0]
    b_id = conn.execute("SELECT id FROM push_deliveries WHERE ticket_id='ticket-b'").fetchone()[0]
    conn.execute("DELETE FROM push_ticket_parents")
    conn.execute(
        "INSERT INTO push_ticket_parents(ticket_id,push_delivery_id,claimed_at) VALUES ('ticket-a',?,'2000-01-01T00:00:00+00:00')",
        (b_id,),
    )
    conn.commit()

    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('corrupt parentage must fail closed before provider lookup')

    assert events.reconcile_push_receipts(
        conn, 'account-a', min_age_seconds=0, post=post
    ) == 0
    assert calls == []
    row = conn.execute(
        "SELECT receipt_status FROM push_deliveries WHERE id=?", (a_id,)
    ).fetchone()
    assert row['receipt_status'] is None
    conn.close()


def test_backup_restore_preserves_exact_parent_relations(tmp_path):
    source = tmp_path / 'source.sqlite'
    backup = tmp_path / 'backup.sqlite'
    restored = tmp_path / 'restored.sqlite'

    conn = _connect(source)
    events.ensure_event_table(conn)
    recovery._ensure_decision_parentage(conn)
    conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at,decision_id
           ) VALUES ('account-a','current-event',1,'TED','new_high_match',91,
                     '2026-08-27T13:00:00+00:00',777)"""
    )
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,
               last_attempt_at,expo_push_token
           ) VALUES (1,42,'ticket-restored','2026-08-27T13:01:00+00:00',1,
                     '2026-08-27T13:01:00+00:00','ExpoPushToken[restore]')"""
    )
    delivery_id = conn.execute(
        "SELECT id FROM push_deliveries WHERE ticket_id='ticket-restored'"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO push_ticket_parents(ticket_id,push_delivery_id,claimed_at) VALUES ('ticket-restored',?,'2026-08-27T13:01:00+00:00')",
        (delivery_id,),
    )
    conn.commit()
    before = _snapshot_current(conn)

    with sqlite3.connect(str(backup)) as backup_conn:
        conn.backup(backup_conn)
    conn.close()
    with sqlite3.connect(str(backup)) as backup_conn, sqlite3.connect(str(restored)) as restored_conn:
        backup_conn.backup(restored_conn)

    restored_conn = _connect(restored)
    assert restored_conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    after = _snapshot_current(restored_conn)
    assert after == before
    restored_conn.close()


def _snapshot_current(conn):
    event = tuple(
        conn.execute(
            "SELECT account_id,event_key,decision_id FROM opportunity_events WHERE event_key='current-event'"
        ).fetchone()
    )
    parent = tuple(
        conn.execute(
            "SELECT ticket_id,push_delivery_id FROM push_ticket_parents WHERE ticket_id='ticket-restored'"
        ).fetchone()
    )
    delivery = tuple(
        conn.execute(
            "SELECT id,event_id,ticket_id FROM push_deliveries WHERE ticket_id='ticket-restored'"
        ).fetchone()
    )
    return event, parent, delivery
