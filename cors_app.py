"""Production WSGI entrypoint with a global CORS safety net."""
import os
from urllib.parse import urlsplit, urlunsplit
from flask import jsonify, request

from api import APP, bp as MOBILE_API_BP
# Import registers the isolated, authenticated Outcome Capture blueprint on APP.
import opportunity_outcome_api as _opportunity_outcome_api
from auth_context import configured_identity, InvalidTokenError

# api.py owns the mobile API blueprint; register it here because this is the
# production WSGI entrypoint and keeps registration explicit at the boundary.
if "mobile_api" not in APP.blueprints:
    APP.register_blueprint(MOBILE_API_BP)


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
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ObraSignal-API"] = "v1"
    response.headers["X-ObraSignal-Build"] = os.getenv("OBRASIGNAL_BUILD") or os.getenv("RENDER_GIT_COMMIT") or "unversioned"
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


def _opportunity_detail(opportunity_id):
    """Fallback authenticated detail including current source lifecycle."""
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401

    from api import _db, _latest_decisions, _row
    from opportunity_lifecycle import ensure_lifecycle_table
    from opportunity_workflow import get_workflow

    c = _db()
    try:
        ensure_lifecycle_table(c)
        row = c.execute(
            """SELECT t.*, COALESCE(lc.is_actionable,1) AS is_actionable,
                      lc.lifecycle_status, lc.lifecycle_reason,
                      lc.source_updated_at AS lifecycle_source_updated_at,
                      lc.last_observed AS lifecycle_last_observed
               FROM tenders t
               LEFT JOIN opportunity_lifecycle lc
                 ON lc.source=t.source AND lc.external_id=t.external_id
               WHERE t.id=?""",
            (opportunity_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "not_found"}), 404
        decision = _latest_decisions(c, identity.account_id, [row["external_id"]]).get((row["source"], row["external_id"]))
        item = _row(row, decision, get_workflow(c, identity.account_id, row["source"], row["external_id"]))
        return jsonify(item)
    finally:
        c.close()


# Keep this route at the production WSGI boundary because the API blueprint
# predates the detail endpoint. It is still protected by the same verified
# provider identity and uses the same account-scoped decision/workflow helpers.
if not any(rule.rule == "/api/v1/opportunities/<int:opportunity_id>" for rule in APP.url_map.iter_rules()):
    APP.add_url_rule(
        "/api/v1/opportunities/<int:opportunity_id>",
        endpoint="mobile_api.opportunity_detail",
        view_func=_opportunity_detail,
        methods=["GET"],
    )


@APP.after_request
def _global_api_cors(response):
    if request.path.startswith("/api/v1/"):
        return _cors(response)
    return response


# Gunicorn imports this module before it starts accepting requests. Complete all
# idempotent schema/read-model work and install additive global-source runtimes
# before allowing the ingestion worker to run.
import app as _app
from app import db, init_db, start_background_worker
from opportunity_lifecycle import ensure_lifecycle_table
from opportunity_outcome import ensure_outcome_table
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
    ensure_lifecycle_table(_lifecycle_conn)
    ensure_outcome_table(_lifecycle_conn)
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
