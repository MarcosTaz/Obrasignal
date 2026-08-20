"""Production WSGI entrypoint with a global CORS safety net."""
import os
from urllib.parse import urlsplit, urlunsplit
from flask import request

# Install the sync-funnel thread hook BEFORE importing api/preload/app. The
# latter imports app, which starts its worker during module initialization.
# Loading the hook first guarantees that the worker is wrapped with the
# account-scoped decision pipeline before its thread starts.
import sync_funnel_hook  # noqa: F401
from api import APP
from auth_context import configured_identity, InvalidTokenError


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
    return response


@APP.before_request
def _global_api_preflight():
    if request.path.startswith("/api/v1/") and request.method == "OPTIONS":
        return _cors(APP.response_class("", status=204, mimetype="text/plain"))
    return None


@APP.before_request
def _protect_radar_api():
    if request.path != "/api/v1/radar":
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        response = APP.jsonify({"error": "authentication_required"})
        return _cors(response), 401
    request.obrasignal_identity = identity
    return None


@APP.before_request
def _stats_safety_net():
    """Keep the dashboard counters available even if an optional stats query fails."""
    if request.path != "/api/v1/stats" or request.method != "GET":
        return None
    try:
        identity = getattr(request, "obrasignal_identity", None) or configured_identity()
        from api import _db, _iso_now
        from decision_log import ensure_decision_table
        c = _db()
        ensure_decision_table(c)
        account_id = identity.account_id
        latest = """LEFT JOIN (
            SELECT od.source, od.external_id, od.decision, od.score, od.id
            FROM opportunity_decisions od
            JOIN (
                SELECT source, external_id, MAX(id) AS max_id
                FROM opportunity_decisions
                WHERE account_id=?
                GROUP BY source, external_id
            ) x ON x.max_id=od.id
            WHERE od.account_id=?
        ) d ON d.source=t.source AND d.external_id=t.external_id"""
        base = f"FROM tenders t {latest}"
        total = c.execute(f"SELECT COUNT(*) {base} WHERE COALESCE(d.decision,'RELEVANT') != 'REJECT'", (account_id, account_id)).fetchone()[0]
        high = c.execute(f"SELECT COUNT(*) {base} WHERE COALESCE(d.score,t.score) >= 75 AND COALESCE(d.decision,'RELEVANT') != 'REJECT'", (account_id, account_id)).fetchone()[0]
        open_count = c.execute(f"SELECT COUNT(*) {base} WHERE COALESCE(d.decision,'RELEVANT') != 'REJECT' AND (t.deadline IS NULL OR t.deadline='' OR datetime(t.deadline)>=datetime('now'))", (account_id, account_id)).fetchone()[0]
        new24 = c.execute(f"SELECT COUNT(*) {base} WHERE COALESCE(d.decision,'RELEVANT') != 'REJECT' AND julianday(t.first_seen)>=julianday('now','-1 day')", (account_id, account_id)).fetchone()[0]
        try:
            last = c.execute("SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
            last_sync = last[0] if last else None
        except Exception:
            last_sync = None
        c.close()
        response = APP.jsonify({"total": total, "high": high, "open": open_count, "new24": new24, "last_sync": last_sync, "account_id": account_id})
        return _cors(response)
    except Exception:
        # Do not take the whole Radar down because dashboard counters failed.
        response = APP.jsonify({"total": 0, "high": 0, "open": 0, "new24": 0, "last_sync": None, "account_id": getattr(getattr(request, "obrasignal_identity", None), "account_id", None), "degraded": True})
        return _cors(response)


@APP.after_request
def _global_api_cors(response):
    if request.path.startswith("/api/v1/"):
        return _cors(response)
    return response
