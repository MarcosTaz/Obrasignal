import api
import cors_app


def test_api_import_keeps_profile_endpoint():
    routes = {rule.rule for rule in api.APP.url_map.iter_rules()}
    assert "/api/v1/profile" in routes


def test_production_wsgi_registers_opportunity_detail_endpoint():
    routes = {rule.rule for rule in cors_app.APP.url_map.iter_rules()}
    assert "/api/v1/opportunities/<int:opportunity_id>" in routes


def test_production_detail_rejects_missing_identity(monkeypatch):
    from jwt import InvalidTokenError

    monkeypatch.setattr(cors_app, "configured_identity", lambda: (_ for _ in ()).throw(InvalidTokenError("missing")))
    response = cors_app.APP.test_client().get("/api/v1/opportunities/1")

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
