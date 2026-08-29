"""Production WSGI entrypoint with a global CORS safety net."""
import json
import os
from urllib.parse import urlsplit, urlunsplit
from flask import jsonify, request

from api import APP, bp as MOBILE_API_BP
from account_privacy import bp as ACCOUNT_PRIVACY_BP
from auth_context import configured_identity, InvalidTokenError
from auth_context_jwt import authentication_health
import notification_privacy_lifecycle as _notification_privacy_lifecycle
import opportunity_watchlist_api as _opportunity_watchlist_api

# api.py owns the mobile API blueprint; account_privacy.py owns authenticated
# export/deletion. Register each public owner explicitly and idempotently at the
# production WSGI boundary so implemented routes cannot remain test-only truth.
if "mobile_api" not in APP.blueprints:
    APP.register_blueprint(MOBILE_API_BP)
if "account_privacy" not in APP.blueprints:
    APP.register_blueprint(ACCOUNT_PRIVACY_BP)


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
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ObraSignal-API"] = "v1"
    response.headers["X-ObraSignal-Build"] = os.getenv("OBRASIGNAL_BUILD") or os.getenv("RENDER_GIT_COMMIT") or "unversioned"
    return response


def _decorate_health(response):
    """Add bounded auth readiness metadata without exposing provider secrets."""
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


# Gunicorn imports this module before it starts accepting requests. Complete all
# idempotent schema/read-model work and install additive global-source runtimes
# before allowing the ingestion worker to run.
import app as _app
from app import db, init_db, start_background_worker
from storage_migration_lock import run_serialized_schema_init
from opportunity_lifecycle import ensure_lifecycle_table
from lifecycle_read_model import install as install_lifecycle_read_model
from notification_dispatch_guard import install as install_notification_dispatch_guard
from notification_event_recovery import (
    initialize_existing_account_baselines,
    install as install_notification_event_recovery,
)
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

run_serialized_schema_init(init_db, _app.DB)
_lifecycle_conn = db()
try:
    ensure_lifecycle_table(_lifecycle_conn)
    initialize_existing_account_baselines(
        _lifecycle_conn,
        _preload.list_active_accounts(_lifecycle_conn),
    )
    _lifecycle_conn.commit()
finally:
    _lifecycle_conn.close()
install_lifecycle_read_model(_preload)
install_notification_dispatch_guard()
install_notification_event_recovery(_preload)
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
