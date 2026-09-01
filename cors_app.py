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

PUBLISHED_FALLBACK_ORIGIN = "https://marcostaz.github.io"

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
    configured_fallback = _normalized_origin(os.getenv("OBRASIGNAL_CORS_FALLBACK_ORIGIN") or "")
    published_fallback = _normalized_origin(PUBLISHED_FALLBACK_ORIGIN)
    # The exact Pages publisher is controlled by the same ObraSignal account and
    # is the production fallback used by the release gate while canonical DNS is
    # unavailable. Keep it code-level so a lagging Render env sync cannot break
    # browser CORS. No wildcard or third-party origin is introduced.
    return tuple(dict.fromkeys(origin for origin in (canonical, configured_fallback, published_fallback) if origin))


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
    if request.path != "/api/v1/health" or not response.is_json:
        return response
    payload = response.get_json(silent=True)
    if not isinstance(payload, dict):
        return response
    payload["auth"] = authentication_health()
    warm = globals().get("AUTH_WARM_STATE")
    payload["runtime"] = {
        "auth_warm_status": warm.get("status") if isinstance(warm, dict) else "initializing",
        "preflight_first": bool(
            APP.before_request_funcs.get(None)
            and APP.before_request_funcs[None][0] is _global_api_preflight
        ),
    }
    response.set_data(json.dumps(payload, separators=(",", ":")))
    return response


@APP.before_request
def _global_api_preflight():
    if request.path.startswith("/api/v1/") and request.method == "OPTIONS":
        return _cors(APP.response_class("", status=204, mimetype="text/plain"))
    return None


# Do this in the module that Render demonstrably imports, not only in an optional
# wrapper entrypoint. `api` registers global billing guards transitively before
# this function exists, so the decorator alone does not make OPTIONS first.
_global_hooks = APP.before_request_funcs.setdefault(None, [])
if _global_api_preflight in _global_hooks:
    _global_hooks.remove(_global_api_preflight)
_global_hooks.insert(0, _global_api_preflight)


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


# Every Gunicorn worker imports this module independently. Startup DDL/WAL work
# is serialized across those processes, while process-local runtime patches are
# installed in each worker before it can serve traffic.
import app as _app
from app import db, init_db, start_background_worker
from bounded_sync import sync_once as bounded_source_sync_once
from decision_refresh import ensure_decision_input_table, record_account_decisions
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
from runtime_db_hardening import install as install_runtime_db_hardening
from push_schema_fastpath import install as install_push_schema_fastpath
from runtime_deferred_worker import start_source_worker_after_readiness
from runtime_leader import acquire_runtime_leader, serialized_startup
import preload as _preload
import push_runtime as _push_runtime

with serialized_startup():
    init_db()
    _lifecycle_conn = db()
    try:
        ensure_evaluation_schema(_lifecycle_conn)
        ensure_lifecycle_table(_lifecycle_conn)
        ensure_traffic_schema(_lifecycle_conn)
        ensure_push_schema(_lifecycle_conn)
        ensure_decision_input_table(_lifecycle_conn)
        _lifecycle_conn.commit()
    finally:
        _lifecycle_conn.close()
    # WAL mode is persistent but PRAGMA journal_mode can itself require a lock;
    # serialize it with migrations so a second HTTP worker cannot race startup.
    install_runtime_db_hardening(_preload, _app)

# All push objects now exist, so install a read-only steady-state schema check
# that still delegates to the real migrator for any fresh/legacy connection.
install_push_schema_fastpath(_push_runtime)

# Select both the bounded source writer and incremental account scorer before any
# elected background leader can run. Every HTTP worker receives identical read
# models and source runtime wiring, but only one process owns scheduled writes.
_preload._original_sync_once = bounded_source_sync_once
_preload._record_account_decisions = record_account_decisions

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

# A process-lifetime non-blocking lease prevents duplicate ingestion/push loops
# when Gunicorn has multiple workers. Follower workers remain dedicated capacity
# for customer HTTP requests while the leader refreshes procurement data. Heavy
# source ingestion is deliberately delayed beyond the deployment readiness
# window so an exact-build health response cannot be followed by a 20s customer
# timeout. Push scheduling stays live immediately because it is lightweight and
# customer-facing push preferences must remain available during that grace.
if acquire_runtime_leader():
    start_source_worker_after_readiness(start_background_worker)
    start_push_scheduler()

# Warm auth here as the authoritative WSGI module. Production telemetry proved
# that Render was serving exact builds with provider_status=uninitialized even
# though production_entrypoint.py contained a warm call, which means the live
# service can bypass that wrapper. Every import path that serves APP now executes
# the same non-fatal, fail-closed warm before Gunicorn can expose the worker.
from runtime_auth_warm import warm_production_auth
AUTH_WARM_STATE = warm_production_auth()
