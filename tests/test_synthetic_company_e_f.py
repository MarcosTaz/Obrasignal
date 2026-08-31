import sqlite3

import app
import account_registry
import opportunity_watchlist_api  # noqa: F401 - controlled candidate API registration
from api import APP


def _configure(monkeypatch, tmp_path, account_id="company-a"):
    database = tmp_path / "company-e-f.db"
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
            """INSERT INTO tenders(
                   source,external_id,title,description,buyer,country,cpv,value,deadline,
                   publication_date,url,first_seen,last_seen,market
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "OBRASIGNAL_SYNTHETIC", "HOSTILE-1", "Synthetic public opportunity",
                "Global opportunity content; tenant-private workflow must never leak.",
                "Synthetic Buyer", "PRT", "45000000", None,
                "2099-12-31T23:59:00+00:00", "2026-08-29",
                "https://example.invalid/hostile-1", "2026-08-29T00:00:00+00:00",
                "2026-08-29T00:00:00+00:00", "PT",
            ),
        )
        conn.commit()
        opportunity_id = conn.execute(
            "SELECT id FROM tenders WHERE source='OBRASIGNAL_SYNTHETIC' AND external_id='HOSTILE-1'"
        ).fetchone()[0]
    finally:
        conn.close()
    return database, opportunity_id


def test_synthetic_company_e_guessed_global_id_never_leaks_company_a_private_state(monkeypatch, tmp_path):
    database, opportunity_id = _configure(monkeypatch, tmp_path, "company-a")
    client = APP.test_client()

    profile_a = client.post(
        "/api/v1/profile",
        json={"name": "Company A Private", "activity": "construção", "coverage_mode": "portugal"},
    )
    assert profile_a.status_code == 200
    assert client.post(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 200
    private = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "REVIEWING", "priority": "HIGH", "note": "PRIVATE-COMPANY-A-NOTE"},
    )
    assert private.status_code == 200

    # Hostile tenant guesses the globally visible opportunity id. Global market truth may be visible,
    # but the embedded workflow must be derived for tenant E and cannot contain Company A state.
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-e-hostile")
    hostile_detail = client.get(f"/api/v1/opportunities/{opportunity_id}")
    assert hostile_detail.status_code == 200
    hostile_workflow = hostile_detail.get_json()["workflow"]
    assert hostile_workflow["status"] == "NEW"
    assert hostile_workflow["note"] is None
    assert hostile_workflow["is_saved"] is False
    assert "PRIVATE-COMPANY-A-NOTE" not in str(hostile_detail.get_json())

    # Account-private Watchlist lookup is indistinguishable from absent for the hostile tenant.
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/watch").status_code == 404
    assert client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "WON", "priority": "LOW", "note": "steal"},
    ).status_code == 404
    assert client.delete(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 404

    # Company profile is independently account-scoped; a forged payload account_id is not authority.
    hostile_profile = client.get("/api/v1/profile")
    assert hostile_profile.status_code == 200
    assert hostile_profile.get_json()["profile"]["name"] != "Company A Private"
    forged_profile = client.post(
        "/api/v1/profile",
        json={"account_id": "company-a", "name": "Hostile E", "activity": "construção"},
    )
    assert forged_profile.status_code == 200
    assert forged_profile.get_json()["account_id"] == "company-e-hostile"
    assert forged_profile.get_json()["profile"]["account_id"] == "company-e-hostile"

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    owner_watch = client.get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert owner_watch.status_code == 200
    assert owner_watch.get_json()["saved"]["note"] == "PRIVATE-COMPANY-A-NOTE"
    owner_profile = client.get("/api/v1/profile")
    assert owner_profile.get_json()["profile"]["name"] == "Company A Private"

    # Persistent private state remains one tenant-owned row rather than being overwritten by the attack.
    conn = sqlite3.connect(database)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM opportunity_workflow WHERE account_id='company-a' AND external_id='HOSTILE-1'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_synthetic_company_f_retries_converge_and_invalid_transition_preserves_truth(monkeypatch, tmp_path):
    database, opportunity_id = _configure(monkeypatch, tmp_path, "company-f")
    client = APP.test_client()

    # Simulate a client retry after an unknown response outcome: repeated SAVE converges to one row/timestamp.
    first = client.post(f"/api/v1/opportunities/{opportunity_id}/save")
    retry = client.post(f"/api/v1/opportunities/{opportunity_id}/save")
    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.get_json()["saved"]["saved_at"] == retry.get_json()["saved"]["saved_at"]

    accepted = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "PREPARING", "priority": "HIGH", "note": "canonical-before-failure"},
    )
    assert accepted.status_code == 200

    # Malformed/invalid retry must fail without corrupting the last canonical relationship state.
    rejected = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "NOT_A_REAL_STATE", "priority": "URGENT", "note": "must-not-persist"},
    )
    assert rejected.status_code == 400
    after = client.get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert after.status_code == 200
    state = after.get_json()["saved"]
    assert state["status"] == "PREPARING"
    assert state["priority"] == "HIGH"
    assert state["note"] == "canonical-before-failure"

    # Replaying the accepted workflow mutation is canonical-upsert behavior, not duplicate business truth.
    replay = client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "PREPARING", "note": "canonical-before-failure"},
    )
    assert replay.status_code == 200
    conn = sqlite3.connect(database)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM opportunity_workflow WHERE account_id='company-f' AND source='OBRASIGNAL_SYNTHETIC' AND external_id='HOSTILE-1'"
        ).fetchone()[0]
        assert rows == 1
    finally:
        conn.close()


def test_synthetic_company_e_stale_or_missing_provider_auth_fails_closed(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, "company-e-hostile")
    client = APP.test_client()
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://synthetic.invalid/auth/v1")

    response = client.get("/api/v1/profile")
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
