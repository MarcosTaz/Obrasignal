import api
import cors_app


def test_api_import_keeps_profile_endpoint():
    routes = {rule.rule for rule in api.APP.url_map.iter_rules()}
    assert "/api/v1/profile" in routes


def test_production_health_has_one_public_canonical_route(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "deploy-sha")

    rules = [
        rule
        for rule in cors_app.APP.url_map.iter_rules()
        if rule.rule == "/api/v1/health"
    ]
    response = cors_app.APP.test_client().get("/api/v1/health")

    assert len(rules) == 1
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["service"] == "obrasignal-api"
    assert response.get_json()["version"] == "1"
    assert response.get_json()["build"] == "deploy-sha"
    assert response.get_json()["time"]


def test_production_wsgi_registers_opportunity_detail_endpoint():
    routes = {rule.rule for rule in cors_app.APP.url_map.iter_rules()}
    assert "/api/v1/opportunities/<int:opportunity_id>" in routes


def test_production_detail_rejects_missing_identity(monkeypatch):
    from jwt import InvalidTokenError

    monkeypatch.setattr(cors_app, "configured_identity", lambda: (_ for _ in ()).throw(InvalidTokenError("missing")))
    response = cors_app.APP.test_client().get("/api/v1/opportunities/1")

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
