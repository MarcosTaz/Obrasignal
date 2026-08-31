import sqlite3

import app
from storage_contract import verify_database
from storage_migration_lock import run_serialized_schema_init


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _build_representative_historical_schema(path):
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
                UNIQUE(source, external_id)
            );
            CREATE TABLE sync_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                found INTEGER DEFAULT 0,
                new_items INTEGER DEFAULT 0
            );
            CREATE TABLE accounts(
                account_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'active',
                plan TEXT NOT NULL DEFAULT 'pilot',
                created_at TEXT NOT NULL
            );
            CREATE TABLE company_profiles(
                account_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
                UNIQUE(account_id, source, external_id)
            );
            """
        )
        conn.execute(
            "INSERT INTO tenders(source,external_id,title,score,first_seen,last_seen) VALUES(?,?,?,?,?,?)",
            ("TED", "legacy-opp", "Historical opportunity", 71, "2025-01-01", "2025-01-02"),
        )
        conn.execute(
            "INSERT INTO accounts(account_id,status,plan,created_at) VALUES(?,?,?,?)",
            ("legacy-account", "active", "pilot", "2025-01-01"),
        )
        conn.execute(
            "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            ("legacy-account", '{"sectors":["electrical"]}', "2025-01-02"),
        )
        conn.execute(
            """INSERT INTO opportunity_decisions(
                source,external_id,decision,reason,score,features_json,rule_version,decided_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            ("TED", "legacy-opp", "QUALIFIED", "historical", 71, "{}", "legacy-v0", "2025-01-03"),
        )
        conn.execute(
            """INSERT INTO opportunity_events(
                event_key,tender_id,source,event_type,score,created_at,delivered_at
            ) VALUES(?,?,?,?,?,?,?)""",
            ("legacy:event", 1, "TED", "new_high_match", 71, "2025-01-04", None),
        )
        conn.execute(
            """INSERT INTO opportunity_workflow(
                account_id,source,external_id,status,note,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            ("legacy-account", "TED", "legacy-opp", "REVIEWING", "preserve me", "2025-01-05"),
        )
        conn.commit()
    finally:
        conn.close()


def test_g10_representative_historical_schema_migrates_additively_without_truth_loss(monkeypatch, tmp_path):
    path = tmp_path / "historical-matrix.sqlite"
    _build_representative_historical_schema(path)
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))

    run_serialized_schema_init(app.init_db, path)

    conn = _connect(path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        verify_database(conn)

        tender = conn.execute(
            "SELECT title, score, first_seen, last_seen FROM tenders WHERE source=? AND external_id=?",
            ("TED", "legacy-opp"),
        ).fetchone()
        assert tuple(tender) == ("Historical opportunity", 71, "2025-01-01", "2025-01-02")

        account = conn.execute(
            "SELECT status, plan, created_at, subscription_status FROM accounts WHERE account_id=?",
            ("legacy-account",),
        ).fetchone()
        assert tuple(account) == ("active", "pilot", "2025-01-01", "trial")

        profile = conn.execute(
            "SELECT profile_json, updated_at FROM company_profiles WHERE account_id=?",
            ("legacy-account",),
        ).fetchone()
        assert tuple(profile) == ('{"sectors":["electrical"]}', "2025-01-02")

        decision = conn.execute(
            """SELECT account_id, decision, reason, score, rule_version,
                      profile_fingerprint, opportunity_fingerprint, decided_at
               FROM opportunity_decisions WHERE source=? AND external_id=?""",
            ("TED", "legacy-opp"),
        ).fetchone()
        assert tuple(decision) == (
            "default", "QUALIFIED", "historical", 71, "legacy-v0", None, None, "2025-01-03"
        )

        event = conn.execute(
            "SELECT account_id,event_type,score,created_at,delivered_at FROM opportunity_events WHERE event_key=?",
            ("legacy:event",),
        ).fetchone()
        assert tuple(event) == ("default", "new_high_match", 71, "2025-01-04", None)

        workflow = conn.execute(
            """SELECT status,note,priority,saved_at,updated_at
               FROM opportunity_workflow
               WHERE account_id=? AND source=? AND external_id=?""",
            ("legacy-account", "TED", "legacy-opp"),
        ).fetchone()
        assert tuple(workflow) == ("REVIEWING", "preserve me", "NORMAL", None, "2025-01-05")
    finally:
        conn.close()


def test_g10_second_start_is_schema_and_data_idempotent(monkeypatch, tmp_path):
    path = tmp_path / "historical-idempotent.sqlite"
    _build_representative_historical_schema(path)
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))

    run_serialized_schema_init(app.init_db, path)
    conn = _connect(path)
    try:
        before_schema = tuple(conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall())
        before_counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "tenders", "accounts", "company_profiles", "opportunity_decisions",
                "opportunity_events", "opportunity_workflow"
            )
        }
    finally:
        conn.close()

    run_serialized_schema_init(app.init_db, path)

    conn = _connect(path)
    try:
        after_schema = tuple(conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall())
        after_counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
        assert after_schema == before_schema
        assert after_counts == before_counts
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        verify_database(conn)
    finally:
        conn.close()
