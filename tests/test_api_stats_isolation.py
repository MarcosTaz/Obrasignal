import sqlite3


def _create_tender_table(conn):
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
            source TEXT,
            external_id TEXT,
            deadline TEXT,
            first_seen TEXT,
            score INTEGER,
            publication_date TEXT,
            published_at TEXT
        )"""
    )


def test_stats_counts_only_authenticated_account(monkeypatch, tmp_path):
    import api

    class Identity:
        account_id = "company-a"
        authenticated = True

    db_path = tmp_path / "stats.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = connect()
    try:
        monkeypatch.setattr(api, "configured_identity", lambda: Identity())
        monkeypatch.setattr(api._preload._app, "db", connect)

        _create_tender_table(conn)
        conn.execute(
            "CREATE TABLE opportunity_decisions(id INTEGER PRIMARY KEY, account_id TEXT, source TEXT, external_id TEXT, score INTEGER)"
        )
        conn.executemany(
            "INSERT INTO tenders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "TEST", "a", "2099-01-01", "2099-01-01T00:00:00+00:00", 90, "2099-01-01", None),
                (2, "TEST", "b", "2099-01-01", "2099-01-01T00:00:00+00:00", 80, "2099-01-01", None),
            ],
        )
        conn.executemany(
            "INSERT INTO opportunity_decisions VALUES (?, ?, ?, ?, ?)",
            [
                (1, "company-a", "TEST", "a", 90),
                (2, "company-b", "TEST", "b", 95),
            ],
        )
        conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
        conn.execute("INSERT INTO sync_runs VALUES (1, '2099-01-01T00:00:00+00:00')")
        conn.commit()

        response = api.APP.test_client().get("/api/v1/stats")
        assert response.status_code == 200
        body = response.get_json()
        assert body["account_id"] == "company-a"
        assert body["total"] == 1
        assert body["relevant60"] == 1
        assert body["high"] == 1
        assert body["very_high"] == 1
    finally:
        conn.close()


def test_stats_uses_only_latest_decision_for_each_opportunity(monkeypatch, tmp_path):
    import api

    class Identity:
        account_id = "company-a"
        authenticated = True

    db_path = tmp_path / "latest-stats.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = connect()
    try:
        monkeypatch.setattr(api, "configured_identity", lambda: Identity())
        monkeypatch.setattr(api._preload._app, "db", connect)
        _create_tender_table(conn)
        conn.execute(
            "CREATE TABLE opportunity_decisions(id INTEGER PRIMARY KEY, account_id TEXT, source TEXT, external_id TEXT, score INTEGER)"
        )
        conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
        conn.execute(
            "INSERT INTO tenders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "TEST", "a", "2099-01-01", "2099-01-01T00:00:00+00:00", 90, "2099-01-01", None),
        )
        conn.executemany(
            "INSERT INTO opportunity_decisions VALUES (?, ?, ?, ?, ?)",
            [
                (1, "company-a", "TEST", "a", 90),
                (2, "company-a", "TEST", "a", 40),
            ],
        )
        conn.execute("INSERT INTO sync_runs VALUES (1, '2099-01-01T00:00:00+00:00')")
        conn.commit()

        response = api.APP.test_client().get("/api/v1/stats")
        assert response.status_code == 200
        body = response.get_json()
        assert body["total"] == 1
        assert body["relevant60"] == 0
        assert body["high"] == 0
        assert body["very_high"] == 0
    finally:
        conn.close()


def test_stats_uses_source_publication_time_not_bulk_import_time_for_new24(monkeypatch, tmp_path):
    import api

    class Identity:
        account_id = "company-a"
        authenticated = True

    db_path = tmp_path / "freshness-stats.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = connect()
    try:
        monkeypatch.setattr(api, "configured_identity", lambda: Identity())
        monkeypatch.setattr(api._preload._app, "db", connect)
        _create_tender_table(conn)
        conn.execute(
            "CREATE TABLE opportunity_decisions(id INTEGER PRIMARY KEY, account_id TEXT, source TEXT, external_id TEXT, score INTEGER)"
        )
        conn.execute("CREATE TABLE sync_runs(id INTEGER PRIMARY KEY, finished_at TEXT)")
        conn.executemany(
            "INSERT INTO tenders VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)",
            [
                (1, "TEST", "historical-imported-now", "2099-01-01", 80, "2020-01-01", None),
                (2, "TEST", "actually-new", "2099-01-01", 80, None, None),
            ],
        )
        conn.executemany(
            "INSERT INTO opportunity_decisions VALUES (?, 'company-a', 'TEST', ?, 80)",
            [(1, "historical-imported-now"), (2, "actually-new")],
        )
        conn.execute("INSERT INTO sync_runs VALUES (1, datetime('now'))")
        conn.commit()

        response = api.APP.test_client().get("/api/v1/stats")
        assert response.status_code == 200
        body = response.get_json()
        assert body["total"] == 2
        assert body["new24"] == 1
    finally:
        conn.close()
