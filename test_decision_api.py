import json
import sqlite3

import pytest

import api
import preload
from decision_log import ensure_decision_table, record_decision


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "obrasignal.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_PROFILE_FILE", str(tmp_path / "company_profile.json"))
    # Reloading app is intentionally avoided; the API uses the current application
    # instance and its database factory reads the environment at call time only
    # when DB is re-created. Use the existing test client and monkeypatch db().
    def db():
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(preload._app, "db", db)
    api.bp.record = None
    return preload.APP.test_client(), db_path


def _seed_tender(db_path, source="TED", external_id="X-1"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders (
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
            last_seen TEXT
        )"""
    )
    cur = conn.execute(
        "INSERT INTO tenders(source, external_id, title, country, cpv, score) VALUES (?, ?, ?, ?, ?, ?)",
        (source, external_id, "Construção", "PRT", "45223100-7", 90),
    )
    conn.commit()
    return conn, cur.lastrowid


def test_decision_endpoint_returns_auditable_decision(client):
    http, db_path = client
    conn, tender_id = _seed_tender(db_path)
    ensure_decision_table(conn)
    record_decision(
        conn,
        "TED",
        "X-1",
        "QUALIFIED",
        "cumpre perfil e regras económicas",
        score=90,
        features={"economic_fit": {"status": "FAVOURABLE"}, "geography": {"score": 5}},
        rule_version="test-v1",
    )
    conn.close()

    response = http.get(f"/api/v1/opportunities/{tender_id}/decision")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["decision"]["decision"] == "QUALIFIED"
    assert payload["decision"]["reason"] == "cumpre perfil e regras económicas"
    assert payload["decision"]["rule_version"] == "test-v1"
    assert payload["decision"]["features"]["economic_fit"]["status"] == "FAVOURABLE"


def test_decision_endpoint_returns_404_without_decision(client):
    http, db_path = client
    conn, tender_id = _seed_tender(db_path, external_id="X-2")
    conn.close()

    response = http.get(f"/api/v1/opportunities/{tender_id}/decision")
    assert response.status_code == 404
    assert response.get_json()["error"] == "decision_not_found"
