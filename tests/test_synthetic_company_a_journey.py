import app
import account_registry
import opportunity_watchlist_api  # noqa: F401 - controlled candidate API registration
from api import APP
from storage_recovery import create_backup_artifact, verified_restore_drill


def _configure_company_a(monkeypatch, database):
    monkeypatch.setattr(app, "DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "synthetic-company-a")
    monkeypatch.setattr(
        account_registry,
        "subscription_state",
        lambda account: {"plan": "pilot", "active": True, "source": "synthetic-test", "expires_at": None},
    )


def _insert_synthetic_opportunity():
    conn = app.db()
    try:
        conn.execute(
            """INSERT INTO tenders(
                   source,external_id,title,description,buyer,country,cpv,value,deadline,
                   publication_date,url,score,first_seen,last_seen,market
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "OBRASIGNAL_SYNTHETIC",
                "COMPANY-A-JOURNEY-1",
                "Reabilitação de escola municipal",
                "Empreitada de construção e reabilitação de edifício escolar.",
                "Município Sintético",
                "PRT",
                "45000000",
                None,
                "2099-12-31T23:59:00+00:00",
                "2026-08-29",
                "https://example.invalid/obrasignal/company-a",
                0,
                "2026-08-29T00:00:00+00:00",
                "2026-08-29T00:00:00+00:00",
                "PT",
            ),
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM tenders WHERE source=? AND external_id=?",
            ("OBRASIGNAL_SYNTHETIC", "COMPANY-A-JOURNEY-1"),
        ).fetchone()[0]
    finally:
        conn.close()


def test_synthetic_company_a_profile_discovery_watch_workflow_reauth_restart_and_restore(monkeypatch, tmp_path):
    database = tmp_path / "company-a.db"
    _configure_company_a(monkeypatch, database)
    app.init_db()
    opportunity_id = _insert_synthetic_opportunity()
    client = APP.test_client()

    # Authenticated company bootstrap/onboarding through the current public profile API.
    profile_write = client.post(
        "/api/v1/profile",
        json={
            "name": "Construtora Sintética A",
            "activity": "construção e reabilitação de edifícios",
            "contract_interests": ["reabilitação de escolas", "empreitadas de construção"],
            "coverage_mode": "portugal",
            "countries": ["PRT"],
            "cpv_prefixes": ["45"],
            "economic_min_score": 0,
        },
    )
    assert profile_write.status_code == 200
    assert profile_write.get_json()["account_id"] == "synthetic-company-a"
    assert profile_write.get_json()["profile"]["name"] == "Construtora Sintética A"

    discovered = client.get("/api/v1/opportunities?source=OBRASIGNAL_SYNTHETIC&market=PT&limit=20")
    assert discovered.status_code == 200
    discovered_items = discovered.get_json()["items"]
    assert len(discovered_items) == 1
    assert discovered_items[0]["id"] == opportunity_id
    assert discovered_items[0]["value"] is None, "UNKNOWN economic value must remain UNKNOWN"

    detail = client.get(f"/api/v1/opportunities/{opportunity_id}")
    assert detail.status_code == 200
    assert detail.get_json()["external_id"] == "COMPANY-A-JOURNEY-1"

    saved = client.post(f"/api/v1/opportunities/{opportunity_id}/save")
    assert saved.status_code == 200
    assert saved.get_json()["saved"]["is_saved"] is True

    watched = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "REVIEWING", "priority": "HIGH", "note": "Confirmar visita e caderno de encargos"},
    )
    assert watched.status_code == 200
    assert watched.get_json()["saved"]["priority"] == "HIGH"

    workflow = client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "PREPARING", "note": "Preparar proposta sintética"},
    )
    assert workflow.status_code == 200
    assert workflow.get_json()["workflow"]["status"] == "PREPARING"

    persisted_watch = client.get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert persisted_watch.status_code == 200
    assert persisted_watch.get_json()["saved"]["is_saved"] is True
    assert persisted_watch.get_json()["saved"]["priority"] == "HIGH"
    assert persisted_watch.get_json()["saved"]["status"] == "PREPARING"
    assert persisted_watch.get_json()["saved"]["note"] == "Preparar proposta sintética"

    # Synthetic logout: no provider token means private product APIs fail closed.
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://synthetic.invalid/auth/v1")
    logged_out = client.get("/api/v1/profile")
    assert logged_out.status_code == 401
    assert logged_out.get_json()["error"] == "authentication_required"

    # Synthetic login: re-establish the same authenticated account and recover state.
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "synthetic-company-a")
    relogged_profile = APP.test_client().get("/api/v1/profile")
    assert relogged_profile.status_code == 200
    assert relogged_profile.get_json()["profile"]["name"] == "Construtora Sintética A"
    relogged_watch = APP.test_client().get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert relogged_watch.status_code == 200
    assert relogged_watch.get_json()["saved"]["status"] == "PREPARING"

    # Process-restart equivalent at storage boundary: all request connections are closed;
    # a fresh client/reopened SQLite connection must reconstruct the same durable truth.
    restarted = APP.test_client().get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert restarted.status_code == 200
    assert restarted.get_json()["saved"]["priority"] == "HIGH"

    # Disaster-recovery drill: create-only backup, simulated loss target, verified restore,
    # then point the synthetic runtime at the restored copy and re-read business truth.
    artifact = create_backup_artifact(database, tmp_path / "backup", label="synthetic-company-a")
    restored_db = tmp_path / "restored-company-a.db"
    verified_restore_drill(artifact["artifact"], artifact["manifest"], restored_db)
    _configure_company_a(monkeypatch, restored_db)

    restored_profile = APP.test_client().get("/api/v1/profile")
    restored_watch = APP.test_client().get(f"/api/v1/opportunities/{opportunity_id}/watch")
    assert restored_profile.status_code == 200
    assert restored_profile.get_json()["profile"]["name"] == "Construtora Sintética A"
    assert restored_watch.status_code == 200
    assert restored_watch.get_json()["saved"]["is_saved"] is True
    assert restored_watch.get_json()["saved"]["status"] == "PREPARING"
    assert restored_watch.get_json()["saved"]["priority"] == "HIGH"
    assert restored_watch.get_json()["saved"]["note"] == "Preparar proposta sintética"
