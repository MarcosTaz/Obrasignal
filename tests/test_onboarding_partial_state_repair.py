import api
import onboarding_recovery


def _install_guard():
    if "mobile_api" not in api.APP.blueprints:
        api.APP.register_blueprint(api.bp)
    onboarding_recovery.install()


def test_durable_profile_then_radar_failure_returns_explicit_partial_success(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "partial-repair.db"))
    _install_guard()

    def fail_after_profile_save(_account_id):
        raise RuntimeError("synthetic Radar bootstrap failure")

    monkeypatch.setattr(api, "bootstrap_account", fail_after_profile_save)
    client = api.APP.test_client()
    payload = {
        "name": "Empresa Persistida",
        "activity": "instalações eléctricas",
        "contract_interests": ["instalações eléctricas em escolas"],
        "countries": ["PRT"],
        "min_value": 50000,
        "max_value": 500000,
    }

    response = client.post("/api/v1/profile", json=payload)
    assert response.status_code == 202
    body = response.get_json()
    assert body["ok"] is True
    assert body["profile_saved"] is True
    assert body["profile"]["name"] == "Empresa Persistida"
    assert body["radar_state"] == "RECOVERY_REQUIRED"
    assert body["radar_recalculated"] is None
    assert body["recovery_code"] == "radar_recalculation_incomplete"

    readback = client.get("/api/v1/profile")
    assert readback.status_code == 200
    assert readback.get_json()["profile"]["name"] == "Empresa Persistida"


def test_failure_before_durable_profile_change_is_not_relabelled_as_partial_success(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "pre-save-failure.db"))
    _install_guard()

    def fail_before_save(*_args, **_kwargs):
        raise RuntimeError("synthetic persistence failure")

    monkeypatch.setattr(api, "save_profile", fail_before_save)
    response = api.APP.test_client().post("/api/v1/profile", json={
        "name": "Não Persistida",
        "activity": "construção",
    })

    assert response.status_code == 500
    assert api.APP.test_client().get("/api/v1/profile").get_json()["profile"]["name"] == ""
