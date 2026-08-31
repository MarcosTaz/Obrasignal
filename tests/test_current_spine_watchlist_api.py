import app
import account_registry
import opportunity_watchlist_api  # noqa: F401 - registers controlled candidate API
from api import APP


def _configure(monkeypatch, tmp_path, account_id="company-a"):
    database = tmp_path / "company-a.db"
    monkeypatch.setattr(app, "DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", account_id)
    monkeypatch.setattr(
        account_registry,
        "subscription_state",
        lambda account: {"plan": "pilot", "active": True, "source": "synthetic-test", "expires_at": None},
    )
    app.init_db()
    conn = app.db()
    try:
        conn.execute(
            """INSERT INTO tenders(source, external_id, title, country, deadline, url, first_seen, last_seen)
               VALUES('OBRASIGNAL_SYNTHETIC','COMPANY-A-1','Synthetic school refurbishment','PRT',
                      '2099-01-01T00:00:00+00:00','https://example.invalid/synthetic/company-a-1',
                      '2026-08-29T00:00:00+00:00','2026-08-29T00:00:00+00:00')"""
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM tenders WHERE source='OBRASIGNAL_SYNTHETIC' AND external_id='COMPANY-A-1'"
        ).fetchone()[0]
    finally:
        conn.close()


def test_current_spine_watchlist_api_is_idempotent_tenant_safe_and_mutable(monkeypatch, tmp_path):
    opportunity_id = _configure(monkeypatch, tmp_path)
    client = APP.test_client()

    first = client.post(f"/api/v1/opportunities/{opportunity_id}/save")
    second = client.post(f"/api/v1/opportunities/{opportunity_id}/save")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["saved"]["saved_at"] == second.get_json()["saved"]["saved_at"]

    updated = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "REVIEWING", "priority": "HIGH", "note": "Confirmar visita técnica"},
    )
    assert updated.status_code == 200
    saved = updated.get_json()["saved"]
    assert saved["status"] == "REVIEWING"
    assert saved["priority"] == "HIGH"
    assert saved["note"] == "Confirmar visita técnica"

    listed = client.get("/api/v1/opportunities/saved?priority=HIGH&order=priority")
    assert listed.status_code == 200
    assert listed.get_json()["count"] == 1
    assert listed.get_json()["items"][0]["opportunity_id"] == opportunity_id

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-b")
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/watch").status_code == 404
    assert client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"priority": "LOW"}
    ).status_code == 404
    assert client.delete(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 404

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    owner_state = client.get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert owner_state.status_code == 200
    assert owner_state.get_json()["saved"]["priority"] == "HIGH"


def test_current_spine_watchlist_rejects_client_tenant_and_invalid_state(monkeypatch, tmp_path):
    opportunity_id = _configure(monkeypatch, tmp_path)
    client = APP.test_client()
    assert client.post(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 200

    forged = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"account_id": "company-b", "priority": "HIGH"},
    )
    assert forged.status_code == 400
    assert forged.get_json()["error"] == "unsupported_watchlist_field"
    assert client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"priority": "URGENT"}
    ).status_code == 400
    assert client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"status": "NOT_REAL"}
    ).status_code == 400
