import pytest

import account_registry
import app
import opportunity_watchlist_api  # registers watchlist on api.APP
from api import APP


@pytest.fixture
def gp01_db(monkeypatch, tmp_path):
    db_path = tmp_path / "gp01-combination.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "golden-account-a")
    monkeypatch.setattr(
        account_registry,
        "subscription_state",
        lambda account: {"plan": "pilot", "active": True, "source": "acceptance", "expires_at": None},
    )
    app.init_db()
    conn = app.db()
    conn.executemany(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                "TED", "GP01-OPEN", "Reabilitação de escola", "Pintura e acabamentos",
                "Município Alpha", "PRT", "45442100", "240000 EUR", "2099-10-01",
                "2026-08-20", "https://example.test/gp01-open", 88,
                "2026-08-20", "2026-08-20", "PT",
            ),
            (
                "BASE", "GP01-CLOSED", "Reabilitação de arquivo", "Pintura interior",
                "Município Beta", "PRT", "45442100", "90000 EUR", "2020-01-01",
                "2020-01-01", "https://example.test/gp01-closed", 70,
                "2020-01-01", "2020-01-01", "PT",
            ),
            (
                "TED", "GP01-UNKNOWN", "Obra com dados incompletos", "Informação parcial",
                "Município Gamma", "PRT", None, None, None,
                "2026-08-20", "https://example.test/gp01-unknown", 75,
                "2026-08-20", "2026-08-20", "PT",
            ),
        ],
    )
    conn.commit()
    ids = {
        row[1]: row[0]
        for row in conn.execute(
            "SELECT id, external_id FROM tenders WHERE external_id LIKE 'GP01-%'"
        ).fetchall()
    }
    conn.close()
    return ids


def _list(client, query=""):
    response = client.get(f"/api/v1/opportunities{query}")
    assert response.status_code == 200
    return response.get_json()["items"]


def test_gp01_auth_discover_detail_source_save_and_tenant_readback(gp01_db, monkeypatch):
    client = APP.test_client()
    opportunity_id = gp01_db["GP01-OPEN"]

    open_items = _list(client, "?open=1")
    assert [item["external_id"] for item in open_items] == ["GP01-OPEN"]

    detail_response = client.get(f"/api/v1/opportunities/{opportunity_id}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()
    assert detail["external_id"] == "GP01-OPEN"
    assert detail["source"] == "TED"
    assert detail["url"] == "https://example.test/gp01-open"
    assert detail["deadline_status"]["state"] == "open"
    assert detail["is_open"] is True

    saved_response = client.post(
        f"/api/v1/opportunities/{opportunity_id}/save",
        json={"account_id": "golden-account-b"},
    )
    assert saved_response.status_code == 200
    saved = saved_response.get_json()
    assert saved["account_id"] == "golden-account-a"
    assert saved["saved"]["is_saved"] is True

    watch_a = client.get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert watch_a.status_code == 200
    assert watch_a.get_json()["account_id"] == "golden-account-a"
    assert watch_a.get_json()["saved"]["is_saved"] is True

    list_a = client.get("/api/v1/opportunities/saved")
    assert list_a.status_code == 200
    assert [item["external_id"] for item in list_a.get_json()["items"]] == ["GP01-OPEN"]

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "golden-account-b")
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/watch").status_code == 404
    list_b = client.get("/api/v1/opportunities/saved")
    assert list_b.status_code == 200
    assert list_b.get_json()["items"] == []
    assert client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"priority": "HIGH"}
    ).status_code == 404
    assert client.delete(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 404

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "golden-account-a")
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/watch").status_code == 200


def test_gp01_unknowns_remain_unknown_and_closed_is_not_open(gp01_db):
    client = APP.test_client()

    unknown = client.get(
        f"/api/v1/opportunities/{gp01_db['GP01-UNKNOWN']}"
    ).get_json()
    assert unknown["value"] is None
    assert unknown["deadline"] is None
    assert unknown["deadline_status"]["state"] == "unknown"
    assert unknown["is_open"] is False

    closed = client.get(
        f"/api/v1/opportunities/{gp01_db['GP01-CLOSED']}"
    ).get_json()
    assert closed["deadline_status"]["state"] == "closed"
    assert closed["is_open"] is False
    assert all(item["external_id"] != "GP01-CLOSED" for item in _list(client, "?open=1"))


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG-GP-001 FALSE-CLAIM: expired work without stronger current lifecycle evidence "
        "remains is_actionable=true and can appear in the default actionable feed."
    ),
)
def test_gp01_closed_work_is_not_actionable_or_in_default_actionable_feed(gp01_db):
    client = APP.test_client()
    closed = client.get(
        f"/api/v1/opportunities/{gp01_db['GP01-CLOSED']}"
    ).get_json()
    assert closed["is_actionable"] is False
    assert all(item["external_id"] != "GP01-CLOSED" for item in _list(client))


def test_gp01_provider_mode_without_token_fails_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://acceptance.example.supabase.co/auth/v1")
    response = APP.test_client().get("/api/v1/opportunities")
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
