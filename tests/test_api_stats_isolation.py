import sqlite3


def test_stats_counts_only_authenticated_account(monkeypatch):
    import api

    class Identity:
        account_id = "company-a"
        authenticated = True

    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    monkeypatch.setattr(api._preload._app, "db", lambda: conn)

    conn.execute("CREATE TABLE tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, deadline TEXT, first_seen TEXT, score INTEGER)")
    conn.execute("CREATE TABLE opportunity_decisions(id INTEGER PRIMARY KEY, account_id TEXT, source TEXT, external_id TEXT, score INTEGER)")
    conn.executemany(
        "INSERT INTO tenders VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "TEST", "a", "2099-01-01", "2099-01-01T00:00:00+00:00", 90),
            (2, "TEST", "b", "2099-01-01", "2099-01-01T00:00:00+00:00", 80),
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
    assert body["high"] == 1


conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
