"""Production WSGI entrypoint with a global CORS safety net."""
import json
import os
from urllib.parse import urlsplit, urlunsplit
from flask import jsonify, request

from api import APP, bp as MOBILE_API_BP
from auth_context import configured_identity, InvalidTokenError
from auth_context_jwt import authentication_health
from e2e_fixture_api import install as install_e2e_fixture_api

if "mobile_api" not in APP.blueprints:
    APP.register_blueprint(MOBILE_API_BP)
install_e2e_fixture_api(APP)

# Customer Value #542 owns the truth boundary where profile persistence may
# succeed while synchronous Radar recalculation still requires recovery.
from onboarding_recovery import install as install_onboarding_recovery
install_onboarding_recovery()


def _origin():
    value = (os.getenv("OBRASIGNAL_CORS_ORIGIN") or "https://marcostaz.github.io").strip()
    if value == "*":
        return value
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _cors(response):
    origin = _origin()
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-ObraSignal-Version"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ObraSignal-API"] = "v1"
    response.headers["X-ObraSignal-Build"] = os.getenv("OBRASIGNAL_BUILD") or os.getenv("RENDER_GIT_COMMIT") or "unversioned"
    return response


def _decorate_health(response):
    if request.path != "/api/v1/health" or not response.is_json:
        return response
    payload = response.get_json(silent=True)
    if not isinstance(payload, dict):
        return response
    payload["auth"] = authentication_health()
    response.set_data(json.dumps(payload, separators=(",", ":")))
    return response


@APP.before_request
def _global_api_preflight():
    if request.path.startswith("/api/v1/") and request.method == "OPTIONS":
        return _cors(APP.response_class("", status=204, mimetype="text/plain"))
    return None


@APP.before_request
def _protect_radar_api():
    is_detail = request.path.startswith("/api/v1/opportunities/") and not request.path.endswith("/workflow")
    if request.path != "/api/v1/radar" and not is_detail:
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        response = jsonify({"error": "authentication_required"})
        return _cors(response), 401
    request.obrasignal_identity = identity
    return None


@APP.after_request
def _global_api_cors(response):
    if request.path.startswith("/api/v1/"):
        return _cors(_decorate_health(response))
    return response


import app as _app
from app import db, init_db, start_background_worker
from storage_migration_lock import run_serialized_schema_init
from opportunity_lifecycle import ensure_lifecycle_table
from lifecycle_read_model import install as install_lifecycle_read_model
from latvia_runtime import install as install_latvia_runtime
from uk_runtime import install as install_uk_runtime
from ecuador_runtime import install as install_ecuador_runtime
from switzerland_runtime import install as install_switzerland_runtime
from poland_runtime import install as install_poland_runtime
from estonia_runtime import install as install_estonia_runtime
from austria_runtime import install as install_austria_runtime
from lithuania_runtime import install as install_lithuania_runtime
from netherlands_runtime import install as install_netherlands_runtime
from germany_runtime import install as install_germany_runtime
from italy_runtime import install as install_italy_runtime
from canada_buys_runtime import install_canadabuys_runtime
import preload as _preload


def _initialize_persistent_schema():
    init_db()
    lifecycle_conn = db()
    try:
        ensure_lifecycle_table(lifecycle_conn)
        lifecycle_conn.commit()
    finally:
        lifecycle_conn.close()


run_serialized_schema_init(_initialize_persistent_schema, _app.DB)
install_lifecycle_read_model(_preload)
install_latvia_runtime()
install_uk_runtime()
install_ecuador_runtime()
install_switzerland_runtime()
install_poland_runtime()
install_estonia_runtime()
install_austria_runtime()
install_lithuania_runtime()
install_netherlands_runtime()
install_germany_runtime()
install_italy_runtime()
install_canadabuys_runtime(
    _app,
    source_enabled=_preload._global_source_enabled,
    record_blocked=_preload._record_blocked_global_source,
)
start_background_worker()
