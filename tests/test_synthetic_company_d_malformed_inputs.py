import app
import account_registry
import opportunity_watchlist_api  # noqa: F401
from api import APP


def _configure(monkeypatch, tmp_path):
    database = tmp_path / "company-d.db"
    monkeypatch.setattr(app, "DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "synthetic-company-d")
    monkeypatch.setattr(
        account_registry,
        "subscription_state",
        lambda account: {"plan": "pilot", "active": True, "source": "synthetic-test", "expires_at": None},
    )
    app.init_db()
    conn = app.db()
    try:
        conn.execute(
            """INSERT INTO tenders(source,external_id,title,country,deadline,url,first_seen,last_seen,market)
               VALUES('OBRASIGNAL_SYNTHETIC','D-1','Unicode – obra Ç 中文','PRT','2099-12-31T23:59:00+00:00',
                      'https://example.invalid/d-1','2026-08-29','2026-08-29','PT')"""
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM tenders WHERE source='OBRASIGNAL_SYNTHETIC' AND external_id='D-1'"
        ).fetchone()[0]
    finally:
        conn.close()


def test_company_d_malformed_numeric_queries_return_400_not_500(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    client = APP.test_client()

    for path in (
        "/api/v1/opportunities?limit=not-a-number",
        "/api/v1/opportunities?minscore=not-a-number",
        "/api/v1/alerts?limit=not-a-number",
    ):
        response = client.get(path)
        assert response.status_code == 400, (path, response.status_code, response.get_data(as_text=True))
        assert response.is_json
        assert response.get_json()["error"] == "invalid_query_parameter"


def test_company_d_non_object_json_writes_return_400_and_preserve_state(monkeypatch, tmp_path):
    opportunity_id = _configure(monkeypatch, tmp_path)
    client = APP.test_client()

    profile = client.post("/api/v1/profile", json=["not", "an", "object"])
    assert profile.status_code == 400
    assert profile.get_json()["error"] == "json_object_required"

    workflow = client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json=["not", "an", "object"],
    )
    assert workflow.status_code == 400
    assert workflow.get_json()["error"] == "json_object_required"

    current = client.get(f"/api/v1/opportunities/{opportunity_id}/workflow")
    assert current.status_code == 200
    assert current.get_json()["workflow"]["status"] == "NEW"
    assert current.get_json()["workflow"]["note"] is None


def test_company_d_long_note_invalid_transition_and_unicode_are_bounded(monkeypatch, tmp_path):
    opportunity_id = _configure(monkeypatch, tmp_path)
    client = APP.test_client()
    assert client.post(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 200

    long_note = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"note": "x" * 501}
    )
    assert long_note.status_code == 400
    invalid = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"status": "DROP_TABLE"}
    )
    assert invalid.status_code == 400

    unicode_note = "Revisão – aço, façade, 中文, 🚧"
    accepted = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch", json={"note": unicode_note}
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["saved"]["note"] == unicode_note
