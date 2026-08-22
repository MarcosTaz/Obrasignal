"""Production WSGI entrypoint with a global CORS safety net."""
import os
from urllib.parse import urlsplit, urlunsplit
from flask import jsonify, request

import sync_funnel_hook  # noqa: F401
from api import APP, bp as MOBILE_API_BP
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
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
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
    """Serve the authenticated detail shape consumed by the mobile/web client."""
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401

    from api import _db, _latest_decisions, _row
    from opportunity_workflow import get_workflow

    c = _db()
    try:
        row = c.execute("SELECT * FROM tenders WHERE id=?", (opportunity_id,)).fetchone()
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
