import app
import api


def _seed(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "opportunities.db"))
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "customer-a")
    monkeypatch.setattr(app, "DB", str(tmp_path / "opportunities.db"))
    conn = app.db()
    conn.execute(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES ('TED','OPEN-1','Pavilhão escolar','Construção de escola','Município','PRT',
           '45214200','500000 EUR','2099-10-01','2026-08-20','https://example.test/open',88,
           '2026-08-20','2026-08-20','PT')"""
    )
    conn.execute(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES ('BASE','CLOSED-1','Arquivo municipal','Reabilitação','Câmara','PRT',
           '45400000','90000 EUR','2020-01-01','2020-01-01','https://example.test/closed',70,
           '2020-01-01','2020-01-01','PT')"""
    )
    conn.commit()
    open_id = conn.execute("SELECT id FROM tenders WHERE external_id='OPEN-1'").fetchone()[0]
    conn.close()
    return open_id


def test_detail_returns_official_fields_and_account_workflow(monkeypatch, tmp_path):
    opportunity_id = _seed(monkeypatch, tmp_path)
    client = api.APP.test_client()

    saved = client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "PREPARING", "note": "Contactar o município"},
    )
    response = client.get(f"/api/v1/opportunities/{opportunity_id}")

    assert saved.status_code == 200
    assert response.status_code == 200
    body = response.get_json()
    assert body["external_id"] == "OPEN-1"
    assert body["url"] == "https://example.test/open"
    assert body["deadline_status"]["state"] == "open"
    assert body["workflow"]["status"] == "PREPARING"
    assert body["workflow"]["note"] == "Contactar o município"


def test_feed_applies_open_source_and_buyer_search_filters(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    client = api.APP.test_client()

    assert client.get("/api/v1/opportunities?open=1").get_json()["count"] == 1
    assert client.get("/api/v1/opportunities?source=BASE").get_json()["items"][0]["external_id"] == "CLOSED-1"
    assert client.get("/api/v1/opportunities?q=munic%C3%ADpio").get_json()["items"][0]["external_id"] == "OPEN-1"
