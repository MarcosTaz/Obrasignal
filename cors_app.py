"""Production WSGI entrypoint with global HTTP/CORS safety controls."""
import json
import os
from urllib.parse import urlsplit, urlunsplit
from flask import jsonify, request

# Register the account/privacy guard before api.py imports account_registry and
# installs Billing's app-level guard. A deletion-state identity must be blocked
# before any ordinary request path can mutate/recreate customer state.
from account_privacy import bp as ACCOUNT_PRIVACY_BP
import api as _api_module
from api import APP, bp as MOBILE_API_BP
from auth_context import configured_identity, InvalidTokenError
from auth_context_jwt import authentication_health

# api.py owns the mobile API blueprint; account_privacy owns only the bounded
# account export/deletion surface and cross-API deletion-state guard.
if "account_privacy" not in APP.blueprints:
    APP.register_blueprint(ACCOUNT_PRIVACY_BP)
if "mobile_api" not in APP.blueprints:
    APP.register_blueprint(MOBILE_API_BP)


_API_JSON_WRITE_MAX_BYTES = 64 * 1024
_QUERY_TEXT_MAX = 200


def _origin():
    value = (os.getenv("OBRASIGNAL_CORS_ORIGIN") or "https://marcostaz.github.io").strip()
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if value == "*":
        return "*" if auth_mode == "development" else None
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
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
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


def _redact_operability_payload(response):
    """Keep tenant-visible diagnostics useful without exposing exception detail."""
    if request.path != "/api/v1/source-health" or not response.is_json:
        return response
    payload = response.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return response
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        raw_error = item.get("last_error")
        item["has_error"] = bool(raw_error)
        if raw_error:
            item["last_error"] = "redacted"
    response.set_data(json.dumps(payload, separators=(",", ":")))
    return response


def _json_write_path():
    if request.path == "/api/v1/profile":
        return request.method == "POST"
    return (
        request.method == "POST"
        and request.path.startswith("/api/v1/opportunities/")
        and request.path.endswith("/workflow")
    )


def _reject_bad_query():
    """Fail predictably before API handlers can turn malformed abuse into 500s."""
    if request.path == "/api/v1/alerts" and "limit" in request.args:
        try:
            int(request.args.get("limit") or "")
        except (TypeError, ValueError):
            return "limit"
    if request.path in ("/api/v1/opportunities", "/api/v1/radar"):
        for name in ("limit", "minscore"):
            if name in request.args and request.args.get(name) not in (None, ""):
                try:
                    int(request.args.get(name))
                except (TypeError, ValueError):
                    return name
    if request.path == "/api/v1/opportunities" and len(request.args.get("q") or "") > _QUERY_TEXT_MAX:
        return "q"
    if request.path in ("/api/v1/latency", "/api/v1/latency-health") and len(request.args.get("source") or "") > 64:
        return "source"
    return None


@APP.before_request
def _global_api_preflight():
    if request.path.startswith("/api/v1/") and request.method == "OPTIONS":
        return _cors(APP.response_class("", status=204, mimetype="text/plain"))
    return None


@APP.before_request
def _global_api_input_bounds():
    if not request.path.startswith("/api/v1/"):
        return None

    if _json_write_path():
        # Preserve fail-closed authentication precedence: unauthenticated callers
        # do not receive detailed body-validation feedback before identity is
        # established. Use api.py's canonical identity reference so provider
        # unavailability still propagates to the API's 503 handler.
        try:
            identity = _api_module.configured_identity()
        except (RuntimeError, InvalidTokenError):
            return _cors(jsonify({"error": "authentication_required"})), 401
        request.obrasignal_identity = identity

    bad_query = _reject_bad_query()
    if bad_query:
        return _cors(jsonify({"error": "invalid_query_parameter", "parameter": bad_query})), 400

    if not _json_write_path():
        return None
    if not request.is_json:
        return _cors(jsonify({"error": "content_type_must_be_application_json"})), 415
    content_length = request.content_length
    if content_length is not None and content_length > _API_JSON_WRITE_MAX_BYTES:
        return _cors(jsonify({"error": "request_too_large"})), 413
    raw = request.get_data(cache=True)
    if len(raw) > _API_JSON_WRITE_MAX_BYTES:
        return _cors(jsonify({"error": "request_too_large"})), 413
    try:
        payload = request.get_json(silent=False, cache=True)
    except Exception:
        return _cors(jsonify({"error": "malformed_json"})), 400
    if not isinstance(payload, dict):
        return _cors(jsonify({"error": "json_object_required"})), 400
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
        response = _redact_operability_payload(_decorate_health(response))
        return _cors(response)
    return response


# Gunicorn imports this module before it starts accepting requests. Complete all
# persistent startup schema work behind one serialization boundary so current or
# future additive migrations cannot escape the concurrency contract.
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
