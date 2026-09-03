import sqlite3

from opportunity_match_pipeline import RULE_VERSION


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT);
        CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
            source TEXT,
            external_id TEXT,
            title TEXT,
            description TEXT,
            buyer TEXT,
            country TEXT,
            cpv TEXT,
            value TEXT,
            deadline TEXT,
            publication_date TEXT,
            published_at TEXT,
            market TEXT,
            last_seen TEXT
        );
        CREATE TABLE company_profiles(
            account_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE opportunity_decisions(
            id INTEGER PRIMARY KEY,
            account_id TEXT,
            source TEXT,
            external_id TEXT,
            decided_at TEXT,
            rule_version TEXT
        );
        """
    )
    return conn


def _seed(conn, *, profile_updated="2026-08-01T00:00:00+00:00", decided="2026-08-02T00:00:00+00:00", rule_version=RULE_VERSION):
    conn.execute("INSERT INTO sync_runs VALUES(1, '2026-08-31T20:00:00+00:00')")
    conn.execute(
        """INSERT INTO tenders VALUES(
            1,'TEST','one','Roof works','Repair school roof','Buyer','PRT','4526',
            '100000','2099-01-01','2026-08-31','2026-08-31T10:00:00+00:00','PT',
            '2026-08-31T20:00:00+00:00'
        )"""
    )
    conn.execute(
        "INSERT INTO company_profiles VALUES('acct','{}',?)",
        (profile_updated,),
    )
    conn.execute(
        "INSERT INTO opportunity_decisions VALUES(1,'acct','TEST','one',?,?)",
        (decided, rule_version),
    )
    conn.commit()


def test_existing_compatible_decision_is_seeded_without_rescore(monkeypatch):
    import decision_refresh as refresh

    conn = _conn()
    _seed(conn)
    refresh.ensure_decision_input_table(conn)
    calls = []
    monkeypatch.setattr(refresh, "list_active_accounts", lambda _conn: ["acct"])
    monkeypatch.setattr(refresh, "load_profile", lambda _account: {"name": "Builder", "countries": ["PRT"]})
    monkeypatch.setattr(refresh, "persist_and_classify", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert refresh.record_account_decisions(conn) == 0
    assert calls == []
    assert conn.execute("SELECT COUNT(*) FROM opportunity_decision_inputs").fetchone()[0] == 1
    conn.close()


def test_newer_profile_rescores_once_then_unchanged_sync_is_free(monkeypatch):
    import decision_refresh as refresh

    conn = _conn()
    _seed(
        conn,
        profile_updated="2026-08-03T00:00:00+00:00",
        decided="2026-08-02T00:00:00+00:00",
    )
    refresh.ensure_decision_input_table(conn)
    calls = []
    profile = {"name": "Builder", "countries": ["PRT"], "keywords": ["roof"]}
    monkeypatch.setattr(refresh, "list_active_accounts", lambda _conn: ["acct"])
    monkeypatch.setattr(refresh, "load_profile", lambda _account: profile)

    def classify(_conn, row, is_new, **kwargs):
        calls.append((row["external_id"], is_new, kwargs))
        return "QUALIFIED", "ok"

    monkeypatch.setattr(refresh, "persist_and_classify", classify)

    assert refresh.record_account_decisions(conn) == 1
    assert len(calls) == 1
    assert calls[0][2]["profile"] is profile
    assert calls[0][2]["commit"] is False
    assert calls[0][2]["ensure"] is False

    assert refresh.record_account_decisions(conn) == 0
    assert len(calls) == 1
    conn.close()


def test_material_source_change_invalidates_fingerprint(monkeypatch):
    import decision_refresh as refresh

    conn = _conn()
    _seed(conn)
    refresh.ensure_decision_input_table(conn)
    calls = []
    monkeypatch.setattr(refresh, "list_active_accounts", lambda _conn: ["acct"])
    monkeypatch.setattr(refresh, "load_profile", lambda _account: {"name": "Builder", "countries": ["PRT"]})
    monkeypatch.setattr(
        refresh,
        "persist_and_classify",
        lambda _conn, row, is_new, **kwargs: calls.append(row["title"]) or ("REVIEW", "ok"),
    )

    assert refresh.record_account_decisions(conn) == 0  # compatible migration seed
    conn.execute("UPDATE tenders SET title='Roof works extended' WHERE id=1")
    conn.commit()
    assert refresh.record_account_decisions(conn) == 1
    assert calls == ["Roof works extended"]
    conn.close()


def test_legacy_decision_without_rule_version_is_migrated_and_rescored(monkeypatch):
    import decision_refresh as refresh

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT);
        CREATE TABLE tenders(
            id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
            description TEXT, buyer TEXT, country TEXT, cpv TEXT, value TEXT,
            deadline TEXT, publication_date TEXT, published_at TEXT, market TEXT,
            last_seen TEXT
        );
        CREATE TABLE company_profiles(account_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE opportunity_decisions(id INTEGER PRIMARY KEY, account_id TEXT, source TEXT, external_id TEXT, decided_at TEXT);
        INSERT INTO sync_runs VALUES(1, '2026-08-31T20:00:00+00:00');
        INSERT INTO tenders VALUES(1,'TEST','one','Roof works','Repair roof','Buyer','PRT','4526','100000','2099-01-01','2026-08-31','2026-08-31T10:00:00+00:00','PT','2026-08-31T20:00:00+00:00');
        INSERT INTO company_profiles VALUES('acct','{}','2026-08-01T00:00:00+00:00');
        INSERT INTO opportunity_decisions VALUES(1,'acct','TEST','one','2026-08-02T00:00:00+00:00');
        """
    )
    calls = []
    monkeypatch.setattr(refresh, "list_active_accounts", lambda _conn: ["acct"])
    monkeypatch.setattr(refresh, "load_profile", lambda _account: {"name": "Builder", "countries": ["PRT"]})
    monkeypatch.setattr(
        refresh,
        "persist_and_classify",
        lambda _conn, row, is_new, **kwargs: calls.append(row["external_id"]) or ("REVIEW", "ok"),
    )

    assert refresh.record_account_decisions(conn) == 1
    assert calls == ["one"]
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_decisions)")}
    assert "rule_version" in columns
    assert "features_json" in columns
    conn.close()
