"""Production WSGI entrypoint with a global CORS safety net."""
import json
import os
from urllib.parse import urlsplit, urlunsplit
from flask import jsonify, redirect, request

from api import APP, bp as MOBILE_API_BP
from account_privacy import bp as ACCOUNT_PRIVACY_BP, DELETION_LOCKED_STATUSES
from auth_context import configured_identity, InvalidTokenError
from auth_context_jwt import authentication_health
from traffic_analytics import bp as TRAFFIC_ANALYTICS_BP, ensure_traffic_schema
from push_runtime import bp as PUSH_RUNTIME_BP, ensure_push_schema, start_push_scheduler

# Register customer-facing authenticated API owners explicitly at the WSGI boundary.
if "mobile_api" not in APP.blueprints:
    APP.register_blueprint(MOBILE_API_BP)
if "account_privacy" not in APP.blueprints:
    APP.register_blueprint(ACCOUNT_PRIVACY_BP)
if "traffic_analytics" not in APP.blueprints:
    APP.register_blueprint(TRAFFIC_ANALYTICS_BP)
if "push_runtime" not in APP.blueprints:
    APP.register_blueprint(PUSH_RUNTIME_BP)


def _normalized_origin(value):
    value = str(value or "").strip()
    if value == "*":
        return value
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _allowed_origins():
    canonical = _normalized_origin(os.getenv("OBRASIGNAL_CORS_ORIGIN") or "https://obrasignal.com")
    fallback = _normalized_origin(os.getenv("OBRASIGNAL_CORS_FALLBACK_ORIGIN") or "")
    return tuple(origin for origin in (canonical, fallback) if origin)


def _official_web_url():
    value = (os.getenv("OBRASIGNAL_WEB_ORIGIN") or "https://obrasignal.com").strip().rstrip("/")
    return value or "https://obrasignal.com"


def _canonical_root_redirect():
    if request.path == "/":
        return redirect(_official_web_url() + "/", code=302)
    return None


APP.before_request_funcs.setdefault(None, []).insert(0, _canonical_root_redirect)


def _cors(response):
    allowed = _allowed_origins()
    requested = _normalized_origin(request.headers.get("Origin"))
    if "*" in allowed:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif requested and requested in allowed:
        response.headers["Access-Control-Allow-Origin"] = requested
        response.headers["Vary"] = "Origin"
    elif allowed:
        # Non-browser responses have no Origin header. Keep the canonical origin
        # visible for diagnostics without granting an unrequested fallback.
        response.headers["Access-Control-Allow-Origin"] = allowed[0]
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-ObraSignal-Version"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
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
def _lock_private_shell_during_account_deletion():
    if not request.path.startswith("/api/v1/"):
        return None
    if request.path.startswith("/api/v1/account/") or request.path in {"/api/v1/health", "/api/v1/billing/webhook", "/api/v1/analytics/event"}:
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None
    from app import db
    conn = db()
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
        if not exists:
            return None
        row = conn.execute("SELECT status FROM accounts WHERE account_id=?", (str(identity.account_id),)).fetchone()
        status = str(row[0]) if row else None
    finally:
        conn.close()
    if status in DELETION_LOCKED_STATUSES:
        response = jsonify({
            "error": "account_private_data_locked",
            "message": "Os dados privados desta conta estão bloqueados pelo ciclo de eliminação.",
            "status": status,
        })
        return _cors(response), 423
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
# before allowing the ingestion and push workers to run.
import app as _app
from app import db, init_db, start_background_worker
from evaluation_policy import ensure_evaluation_schema
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

init_db()
_lifecycle_conn = db()
try:
    ensure_evaluation_schema(_lifecycle_conn)
    ensure_lifecycle_table(_lifecycle_conn)
    ensure_traffic_schema(_lifecycle_conn)
    ensure_push_schema(_lifecycle_conn)
    _lifecycle_conn.commit()
finally:
    _lifecycle_conn.close()
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
start_push_scheduler()
