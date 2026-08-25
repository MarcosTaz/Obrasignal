import sqlite3

import api
import app
import opportunity_outcome_api  # noqa: F401 - registers isolated blueprint


def setup_db(monkeypatch, tmp_path):
    path = tmp_path / "outcomes-api.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setattr(api._preload._app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    app.init_db()
    conn = app.db()
    conn.execute(
        "INSERT INTO tenders(source, external_id, title, value) VALUES(?,?,?,?)",
        ("TED", "API-1", "Hospital", "900000"),
    )
    conn.commit()
    opportunity_id = conn.execute("SELECT id FROM tenders WHERE external_id='API-1'").fetchone()[0]
    conn.close()
    return opportunity_id, path


def test_api_records_user_confirmed_outcome_and_returns_current_history(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    created = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={
            "outcome_type": "WON",
            "award_value": "810000.25",
            "currency": "EUR",
            "reason_code": "OTHER",
            "note": "Confirmed internally",
            "idempotency_key": "api-win-1",
        },
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["account_id"] == "company-a"
    assert body["outcome"]["source_type"] == "USER_CONFIRMED"
    assert body["outcome"]["award_value"] == "810000.25"

    current = client.get(f"/api/v1/opportunities/{opportunity_id}/outcome")
    assert current.status_code == 200
    assert current.get_json()["outcome"]["outcome_type"] == "WON"

    history = client.get(f"/api/v1/opportunities/{opportunity_id}/outcomes")
    assert history.status_code == 200
    assert history.get_json()["count"] == 1


def test_api_cannot_spoof_account_or_official_source(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    account = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "LOST", "account_id": "company-b"},
    )
    official = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "WON", "source_type": "OFFICIAL_SOURCE", "award_value": "1", "currency": "EUR"},
    )
    assert account.status_code == 400
    assert official.status_code == 400


def test_api_idempotency_retry_and_conflict(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    url = f"/api/v1/opportunities/{opportunity_id}/outcomes"
    payload = {"outcome_type": "NO_SUBMISSION", "idempotency_key": "same-request"}
    first = client.post(url, json=payload)
    retry = client.post(url, json=payload)
    conflict = client.post(url, json={"outcome_type": "LOST", "idempotency_key": "same-request"})
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.get_json()["created"] is False
    assert conflict.status_code == 409


def test_api_correction_appends_version_instead_of_overwriting(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    first = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "LOST", "idempotency_key": "mistake"},
    ).get_json()["outcome"]
    corrected = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/outcomes/{first['outcome_id']}",
        json={
            "outcome_type": "WON",
            "award_value": "100",
            "currency": "EUR",
            "idempotency_key": "fix-1",
        },
    )
    assert corrected.status_code == 201
    current = client.get(f"/api/v1/opportunities/{opportunity_id}/outcome").get_json()["outcome"]
    assert current["outcome_type"] == "WON"
    history = client.get(f"/api/v1/opportunities/{opportunity_id}/outcomes").get_json()["items"]
    assert [row["status"] for row in history] == ["SUPERSEDED", "CURRENT"]


def test_api_cross_tenant_read_and_mutation_are_isolated(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    first = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "LOST"},
    ).get_json()["outcome"]

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-b")
    current = client.get(f"/api/v1/opportunities/{opportunity_id}/outcome")
    assert current.status_code == 200
    assert current.get_json()["outcome"] is None
    history = client.get(f"/api/v1/opportunities/{opportunity_id}/outcomes")
    assert history.get_json()["items"] == []
    patch = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/outcomes/{first['outcome_id']}",
        json={"outcome_type": "WON", "award_value": "1", "currency": "EUR"},
    )
    assert patch.status_code == 404


def test_api_missing_opportunity_invalid_type_and_malformed_money(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    assert client.get("/api/v1/opportunities/999999/outcome").status_code == 404
    invalid = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "MAYBE"},
    )
    money = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "WON", "award_value": "NaN", "currency": "EUR"},
    )
    malformed = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        data="not-json",
        content_type="application/json",
    )
    assert invalid.status_code == 400
    assert money.status_code == 400
    assert malformed.status_code == 400


def test_api_note_is_bounded_json_data_and_opportunity_is_not_mutated(monkeypatch, tmp_path):
    opportunity_id, path = setup_db(monkeypatch, tmp_path)
    client = api.APP.test_client()
    conn = sqlite3.connect(path)
    before = conn.execute("SELECT title, value FROM tenders WHERE id=?", (opportunity_id,)).fetchone()
    conn.close()
    response = client.post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "UNKNOWN", "note": "<script>alert(1)</script>"},
    )
    assert response.status_code == 201
    assert response.content_type.startswith("application/json")
    assert response.get_json()["outcome"]["note"] == "<script>alert(1)</script>"
    conn = sqlite3.connect(path)
    after = conn.execute("SELECT title, value FROM tenders WHERE id=?", (opportunity_id,)).fetchone()
    conn.close()
    assert before == after


def test_api_rejects_oversized_payload_field(monkeypatch, tmp_path):
    opportunity_id, _ = setup_db(monkeypatch, tmp_path)
    response = api.APP.test_client().post(
        f"/api/v1/opportunities/{opportunity_id}/outcomes",
        json={"outcome_type": "UNKNOWN", "note": "x" * 1001},
    )
    assert response.status_code == 400
