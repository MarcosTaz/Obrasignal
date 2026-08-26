"""Authorization-integrity A/B differential guards for tenant-owned state."""
import sqlite3

import api


class _Identity:
    def __init__(self, account_id):
        self.account_id = account_id
        self.authenticated = True


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def test_alert_delivery_foreign_event_id_cannot_mutate_other_tenant(monkeypatch, tmp_path):
    db_path = tmp_path / "alerts-authz.db"
    current = {"account_id": "account-a"}

    def connect():
        return _connect(db_path)

    monkeypatch.setattr(api, "configured_identity", lambda: _Identity(current["account_id"]))
    monkeypatch.setattr(api, "ensure_account", lambda _conn, _account_id: None)
    monkeypatch.setattr(api._preload._app, "db", connect)

    conn = connect()
    conn.execute(
        """CREATE TABLE opportunity_events(
            id INTEGER PRIMARY KEY,
            account_id TEXT NOT NULL,
            event_key TEXT NOT NULL UNIQUE,
            tender_id INTEGER,
            source TEXT,
            event_type TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            delivered_at TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO opportunity_events(id,account_id,event_key,event_type,created_at) VALUES (?,?,?,?,?)",
        [
            (1, "account-a", "account-a:event", "new_high_match", "2026-08-26T00:00:00+00:00"),
            (2, "account-b", "account-b:event", "new_high_match", "2026-08-26T00:00:00+00:00"),
        ],
    )
    conn.commit()
    conn.close()

    client = api.APP.test_client()

    foreign = client.post("/api/v1/alerts/2/delivered")
    assert foreign.status_code == 404
    conn = connect()
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=2").fetchone()[0] is None
    conn.close()

    own = client.post("/api/v1/alerts/1/delivered")
    assert own.status_code == 200
    conn = connect()
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=1").fetchone()[0] is not None
    assert conn.execute("SELECT delivered_at FROM opportunity_events WHERE id=2").fetchone()[0] is None
    conn.close()


def test_shared_opportunity_id_does_not_share_workflow_authority(monkeypatch, tmp_path):
    db_path = tmp_path / "workflow-authz.db"
    current = {"account_id": "account-a"}

    def connect():
        return _connect(db_path)

    monkeypatch.setattr(api, "configured_identity", lambda: _Identity(current["account_id"]))
    monkeypatch.setattr(api, "ensure_account", lambda _conn, _account_id: None)
    monkeypatch.setattr(api._preload._app, "db", connect)

    conn = connect()
    conn.execute("CREATE TABLE tenders(id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL)")
    conn.execute("INSERT INTO tenders(id,source,external_id) VALUES (1,'TEST','shared-opportunity')")
    conn.commit()
    conn.close()

    client = api.APP.test_client()

    response = client.post(
        "/api/v1/opportunities/1/workflow",
        json={"status": "PREPARING", "note": "A only"},
    )
    assert response.status_code == 200
    assert response.get_json()["account_id"] == "account-a"

    current["account_id"] = "account-b"
    b = client.get("/api/v1/opportunities/1/workflow")
    assert b.status_code == 200
    assert b.get_json()["workflow"]["status"] == "NEW"
    assert b.get_json()["workflow"]["note"] is None

    response = client.post(
        "/api/v1/opportunities/1/workflow",
        json={"status": "REVIEWING", "note": "B only"},
    )
    assert response.status_code == 200

    current["account_id"] = "account-a"
    a = client.get("/api/v1/opportunities/1/workflow")
    assert a.status_code == 200
    assert a.get_json()["workflow"]["status"] == "PREPARING"
    assert a.get_json()["workflow"]["note"] == "A only"
