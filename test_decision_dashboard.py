import sqlite3

import pytest

import preload
from decision_log import ensure_decision_table, record_decision


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "obrasignal.db"

    def db():
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(preload._app, "db", db)
    preload.APP.config.update(TESTING=True)
    conn = db()
    conn.execute("""CREATE TABLE tenders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, external_id TEXT NOT NULL,
        title TEXT, description TEXT, buyer TEXT, country TEXT, value TEXT, deadline TEXT,
        url TEXT, score INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()
    return preload.APP.test_client(), db_path


def _seed(db_path, external_id="D-1"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "INSERT INTO tenders(source, external_id, title, buyer, country, value, deadline, url, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("TED", external_id, "Estrutura metálica", "Município", "PRT", "150000", "2099-12-31", "https://example.test", 90),
    )
    ensure_decision_table(conn)
    record_decision(conn, "TED", external_id, "QUALIFIED", "cumpre perfil e regras económicas", score=90,
                    features={"profile_score": 86, "lot_score": 78,
                              "geography": {"score": 5, "reason": "cidade prioritária"},
                              "economic_fit": {"score": 100, "status": "FAVOURABLE", "reason": "valor dentro do intervalo"},
                              "capability_evidence": {"evidence_count": 2, "reason": "foram encontradas capacidades da empresa na descrição"},
                              "hard_capability_blockers": []}, rule_version="test-v1")
    conn.commit()
    conn.close()
    return cur.lastrowid


def test_opportunity_detail_shows_explainable_decision(client):
    http, db_path = client
    tender_id = _seed(db_path)
    response = http.get(f"/opportunity/{tender_id}")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "QUALIFIED" in body
    assert "Geografia" in body
    assert "Economic Fit" in body
    assert "cidade prioritária" in body


def test_opportunity_detail_returns_404_for_unknown(client):
    http, _ = client
    response = http.get("/opportunity/999")
    assert response.status_code == 404
