import sqlite3

import app
from storage_contract import verify_database
from storage_migration_lock import run_serialized_schema_init


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def test_g10_representative_historical_owner_schemas_migrate_without_data_loss(monkeypatch, tmp_path):
    path = tmp_path / "historical-composed.sqlite"
    conn = _connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE tenders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT,
                description TEXT,
                buyer TEXT,
                country TEXT,
                cpv TEXT,
                value TEXT,
                deadline TEXT,
                publication_date TEXT,
                url TEXT,
                score INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT,
                UNIQUE(source,external_id)
            );
            CREATE TABLE opportunity_decisions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                score INTEGER,
                features_json TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                decided_at TEXT NOT NULL
            );
            CREATE TABLE opportunity_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL UNIQUE,
                tender_id INTEGER,
                source TEXT,
                event_type TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            );
            CREATE TABLE opportunity_workflow(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                status TEXT NOT NULL,
                note TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(account_id,source,external_id)
            );
            CREATE TABLE push_devices(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                installation_id TEXT NOT NULL UNIQUE,
                expo_push_token TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                binding_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT
            );
            CREATE TABLE push_deliveries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                push_device_id INTEGER NOT NULL,
                ticket_id TEXT,
                submitted_at TEXT,
                last_error TEXT,
                UNIQUE(event_id,push_device_id)
            );
            """
        )
        tender_id = conn.execute(
            "INSERT INTO tenders(source,external_id,title,score) VALUES(?,?,?,?)",
            ("TED", "historical-g10", "Historical G10 opportunity", 77),
        ).lastrowid
        conn.execute(
            """INSERT INTO opportunity_decisions(
                source,external_id,decision,reason,score,features_json,rule_version,decided_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            ("TED", "historical-g10", "QUALIFIED", "historical", 77, "{}", "commercial-v1", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO opportunity_events(
                event_key,tender_id,source,event_type,score,created_at
            ) VALUES(?,?,?,?,?,?)""",
            ("legacy:event:g10", tender_id, "TED", "new_high_match", 77, "2026-01-01T00:01:00+00:00"),
        )
        conn.execute(
            """INSERT INTO opportunity_workflow(
                account_id,source,external_id,status,note,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            ("legacy-account", "TED", "historical-g10", "REVIEWING", "preserve me", "2026-01-01T00:02:00+00:00"),
        )
        device_id = conn.execute(
            """INSERT INTO push_devices(
                account_id,installation_id,expo_push_token,platform,binding_id,created_at,updated_at,last_error
            ) VALUES(?,?,?,?,?,?,?,?)""",
            ("legacy-account", "legacy-installation", "ExpoPushToken[legacy-g10]", "android", "legacy-binding", "2026-01-01", "2026-01-01", None),
        ).lastrowid
        conn.execute(
            """INSERT INTO push_deliveries(event_id,push_device_id,ticket_id,submitted_at,last_error)
            VALUES(?,?,?,?,?)""",
            (1, device_id, "legacy-ticket", "2026-01-01T00:03:00+00:00", None),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))
    run_serialized_schema_init(app.init_db, path)

    conn = _connect(path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        verify_database(conn)

        tender = conn.execute(
            "SELECT title,score FROM tenders WHERE source=? AND external_id=?",
            ("TED", "historical-g10"),
        ).fetchone()
        assert dict(tender) == {"title": "Historical G10 opportunity", "score": 77}

        decision = conn.execute(
            """SELECT account_id,decision,reason,profile_fingerprint,opportunity_fingerprint
               FROM opportunity_decisions WHERE source=? AND external_id=?""",
            ("TED", "historical-g10"),
        ).fetchone()
        assert decision["account_id"] == "default"
        assert decision["decision"] == "QUALIFIED"
        assert decision["reason"] == "historical"
        assert decision["profile_fingerprint"] is None
        assert decision["opportunity_fingerprint"] is None

        event = conn.execute(
            "SELECT account_id,event_key,score FROM opportunity_events WHERE event_key=?",
            ("legacy:event:g10",),
        ).fetchone()
        assert dict(event) == {"account_id": "default", "event_key": "legacy:event:g10", "score": 77}

        workflow = conn.execute(
            """SELECT status,note,priority,saved_at FROM opportunity_workflow
               WHERE account_id=? AND source=? AND external_id=?""",
            ("legacy-account", "TED", "historical-g10"),
        ).fetchone()
        assert workflow["status"] == "REVIEWING"
        assert workflow["note"] == "preserve me"
        assert workflow["priority"] == "NORMAL"
        assert workflow["saved_at"] is None

        device = conn.execute(
            "SELECT installation_id,revoked_at FROM push_devices WHERE id=?",
            (device_id,),
        ).fetchone()
        assert device["installation_id"] == "legacy-installation"
        assert device["revoked_at"] is None

        delivery = conn.execute(
            """SELECT ticket_id,attempt_count,last_attempt_at,next_attempt_at,receipt_status,failed_at
               FROM push_deliveries WHERE event_id=1 AND push_device_id=?""",
            (device_id,),
        ).fetchone()
        assert delivery["ticket_id"] == "legacy-ticket"
        assert delivery["attempt_count"] == 0
        assert delivery["last_attempt_at"] is None
        assert delivery["next_attempt_at"] is None
        assert delivery["receipt_status"] is None
        assert delivery["failed_at"] is None

        tender_columns = {row[1] for row in conn.execute("PRAGMA table_info(tenders)")}
        assert {"published_at", "match_reason", "priority_label", "priority_class", "market"} <= tender_columns
        decision_columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)")}
        assert {"account_id", "profile_fingerprint", "opportunity_fingerprint"} <= decision_columns
        delivery_columns = {row[1] for row in conn.execute("PRAGMA table_info(push_deliveries)")}
        assert {
            "attempt_count", "last_attempt_at", "next_attempt_at", "expo_push_token",
            "receipt_status", "receipt_checked_at", "receipt_error", "failed_at",
        } <= delivery_columns
    finally:
        conn.close()
