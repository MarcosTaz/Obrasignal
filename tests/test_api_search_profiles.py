import app
import api
import search_profiles_api  # installs profile routes and canonical direct search
from search_profiles import ensure_search_profile_table


def _setup_db(monkeypatch, tmp_path):
    path = tmp_path / "search-profiles.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    app.init_db()
    conn = app.db()
    ensure_search_profile_table(conn)
    conn.execute(
        """INSERT INTO tenders(source,external_id,title,description,buyer,country,cpv,value,deadline,
                                  publication_date,url,score,first_seen,last_seen,market)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("TED", "roof-1", "Roof painting works", "Industrial coating", "Buyer A", "PRT", "45260000",
         "250000", "2099-09-30T12:00:00+00:00", "2026-08-25", "https://example.test/1", 82,
         "2026-08-25T00:00:00+00:00", "2026-08-25T00:00:00+00:00", "PT"),
    )
    conn.execute(
        """INSERT INTO tenders(source,external_id,title,description,buyer,country,cpv,value,deadline,
                                  publication_date,url,score,first_seen,last_seen,market)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("TED", "road-1", "Road construction", "Civil works", "Buyer B", "PRT", "45230000",
         "900000", "2099-10-15T12:00:00+00:00", "2026-08-25", "https://example.test/2", 55,
         "2026-08-25T00:00:00+00:00", "2026-08-25T00:00:00+00:00", "PT"),
    )
    conn.commit()
    conn.close()
    return api.APP.test_client()


def _semantic_search_payload(body):
    return {
        "items": body["items"],
        "count": body["count"],
        "market": body["market"],
        "account_id": body["account_id"],
    }


def test_saved_profile_run_is_semantically_equivalent_to_direct_search(monkeypatch, tmp_path):
    client = _setup_db(monkeypatch, tmp_path)
    direct = client.get("/api/v1/opportunities?market=PT&q=roof&minscore=60&open=1&limit=20")
    assert direct.status_code == 200

    created = client.post(
        "/api/v1/search-profiles",
        json={
            "name": "Roof PT 60+",
            "filters": {"market": "PT", "q": "roof", "minscore": 60, "open": True},
            "sort": "score_desc_deadline_asc",
        },
    )
    assert created.status_code == 201
    profile_id = created.get_json()["profile"]["profile_id"]

    saved = client.post(f"/api/v1/search-profiles/{profile_id}/run?limit=20", json={})
    assert saved.status_code == 200
    assert _semantic_search_payload(saved.get_json()) == _semantic_search_payload(direct.get_json())


def test_crud_is_tenant_scoped_and_payload_cannot_choose_account(monkeypatch, tmp_path):
    client = _setup_db(monkeypatch, tmp_path)
    bad = client.post(
        "/api/v1/search-profiles",
        json={"account_id": "account-b", "name": "Injected", "filters": {}},
    )
    assert bad.status_code == 400

    created = client.post(
        "/api/v1/search-profiles",
        json={"name": "A only", "filters": {"market": "PT"}, "is_default": True},
    )
    assert created.status_code == 201
    profile_id = created.get_json()["profile"]["profile_id"]
    assert created.get_json()["account_id"] == "account-a"

    assert client.post(
        f"/api/v1/search-profiles/{profile_id}/run",
        json={"account_id": "account-b"},
    ).status_code == 400

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-b")
    assert client.get(f"/api/v1/search-profiles/{profile_id}").status_code == 404
    assert client.patch(f"/api/v1/search-profiles/{profile_id}", json={"name": "stolen"}).status_code == 404
    assert client.post(f"/api/v1/search-profiles/{profile_id}/run", json={}).status_code == 404
    assert client.delete(f"/api/v1/search-profiles/{profile_id}").status_code == 404

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    own = client.get(f"/api/v1/search-profiles/{profile_id}")
    assert own.status_code == 200
    assert own.get_json()["profile"]["name"] == "A only"


def test_default_profile_is_unique_via_api_and_delete_is_hard_delete(monkeypatch, tmp_path):
    client = _setup_db(monkeypatch, tmp_path)
    first = client.post("/api/v1/search-profiles", json={"name": "First", "filters": {}, "is_default": True}).get_json()["profile"]
    second = client.post("/api/v1/search-profiles", json={"name": "Second", "filters": {}, "is_default": True}).get_json()["profile"]

    listing = client.get("/api/v1/search-profiles")
    assert listing.status_code == 200
    items = {item["profile_id"]: item for item in listing.get_json()["items"]}
    assert items[first["profile_id"]]["is_default"] is False
    assert items[second["profile_id"]]["is_default"] is True

    removed = client.delete(f"/api/v1/search-profiles/{first['profile_id']}")
    assert removed.status_code == 200
    assert client.get(f"/api/v1/search-profiles/{first['profile_id']}").status_code == 404


def test_api_rejects_unknown_filters_sort_and_bad_query_values(monkeypatch, tmp_path):
    client = _setup_db(monkeypatch, tmp_path)
    assert client.post(
        "/api/v1/search-profiles",
        json={"name": "Unknown", "filters": {"deadline_within_days": 10}},
    ).status_code == 400
    assert client.post(
        "/api/v1/search-profiles",
        json={"name": "Unsafe sort", "filters": {}, "sort": "deadline DESC; DROP TABLE tenders"},
    ).status_code == 400
    assert client.get("/api/v1/opportunities?minscore=not-a-number").status_code == 400
    assert client.get("/api/v1/opportunities?country=Portugal").status_code == 400
