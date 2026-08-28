from flask import Flask
from jwt import InvalidTokenError

from auth_context_jwt import JwksUnavailableError
from cloud_switching.web import create_blueprint
from cloud_switching.workspace import DecisionWorkspace


def app_for(resolver):
    app = Flask(__name__)
    app.register_blueprint(create_blueprint(workspace=DecisionWorkspace(), resolve_tenant=resolver))
    return app


def test_invalid_canonical_token_maps_to_401_not_500():
    def resolver():
        raise InvalidTokenError("bad token")

    response = app_for(resolver).test_client().get("/cloud-switching/api/packages/x")
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"


def test_canonical_jwks_outage_maps_to_503_not_401_or_500():
    def resolver():
        raise JwksUnavailableError("unavailable")

    response = app_for(resolver).test_client().get("/cloud-switching/api/packages/x")
    assert response.status_code == 503
    assert response.get_json()["error"] == "authentication_service_unavailable"


def test_invalid_auth_configuration_fails_closed_as_401():
    def resolver():
        raise RuntimeError("bad auth configuration")

    response = app_for(resolver).test_client().get("/cloud-switching/api/packages/x")
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"


def test_health_does_not_require_customer_identity():
    def resolver():
        raise AssertionError("health must not invoke tenant resolver")

    response = app_for(resolver).test_client().get("/cloud-switching/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
