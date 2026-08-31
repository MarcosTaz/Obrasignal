"""Account-private saved-opportunity API.

This is a thin HTTP adapter over opportunity_workflow. It intentionally keeps
watch state separate from the source lifecycle stored on canonical opportunities.
"""
from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from api import APP, _db, _deadline_state, _iso_now
from auth_context import configured_identity
from account_registry import ensure_account
from opportunity_workflow import (
    get_saved_opportunity,
    list_saved_opportunities,
    save_opportunity,
    unsave_opportunity,
    update_saved_opportunity,
)

bp = Blueprint("opportunity_watchlist_api", __name__, url_prefix="/api/v1")


@bp.before_request
def _require_identity():
    if request.method == "OPTIONS":
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({"error": "authentication_required"}), 401
    request.obrasignal_identity = identity
    conn = _db()
    try:
        ensure_account(conn, identity.account_id)
    finally:
        conn.close()
    return None


@bp.after_request
def _watchlist_cors(response):
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-ObraSignal-Version, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    response.headers["Cache-Control"] = "no-store"
    return response


def _saved_payload(item):
    if item is None:
        return None
    payload = dict(item)
    if "deadline" in payload:
        payload["deadline_status"] = _deadline_state(payload.get("deadline"))
    return payload


@bp.route("/opportunities/saved", methods=["GET"])
def saved_opportunities():
    identity = request.obrasignal_identity
    status = request.args.get("status")
    priority = request.args.get("priority")
    order = request.args.get("order", "recent")
    try:
        limit = int(request.args.get("limit", 20) or 20)
        offset = int(request.args.get("offset", 0) or 0)
    except ValueError:
        return jsonify({"error": "invalid_pagination"}), 400
    conn = _db()
    try:
        items = list_saved_opportunities(
            conn,
            identity.account_id,
            status=status,
            priority=priority,
            order=order,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "items": [_saved_payload(item) for item in items],
            "count": len(items),
            "limit": max(1, min(100, limit)),
            "offset": max(0, offset),
            "account_id": identity.account_id,
            "generated_at": _iso_now(),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


@bp.route("/opportunities/<int:opportunity_id>/save", methods=["POST", "DELETE"])
def saved_opportunity_membership(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        if request.method == "POST":
            item = save_opportunity(conn, identity.account_id, opportunity_id)
            return jsonify({
                "ok": True,
                "saved": _saved_payload(item),
                "account_id": identity.account_id,
                "generated_at": _iso_now(),
            })
        removed = unsave_opportunity(conn, identity.account_id, opportunity_id)
        if not removed:
            return jsonify({"error": "saved_opportunity_not_found"}), 404
        return jsonify({
            "ok": True,
            "opportunity_id": opportunity_id,
            "is_saved": False,
            "account_id": identity.account_id,
            "generated_at": _iso_now(),
        })
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    finally:
        conn.close()


@bp.route("/opportunities/<int:opportunity_id>/watch", methods=["GET", "PATCH"])
def saved_opportunity_state(opportunity_id):
    identity = request.obrasignal_identity
    conn = _db()
    try:
        if request.method == "GET":
            try:
                item = get_saved_opportunity(conn, identity.account_id, opportunity_id)
            except LookupError:
                return jsonify({"error": "not_found"}), 404
            if item is None:
                return jsonify({"error": "saved_opportunity_not_found"}), 404
            return jsonify({
                "saved": _saved_payload(item),
                "account_id": identity.account_id,
                "generated_at": _iso_now(),
            })

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        supported = {"status", "priority", "note"}
        if any(key not in supported for key in payload):
            return jsonify({"error": "unsupported_watchlist_field"}), 400
        item = update_saved_opportunity(
            conn,
            identity.account_id,
            opportunity_id,
            status=payload.get("status") if "status" in payload else None,
            priority=payload.get("priority") if "priority" in payload else None,
            note=payload.get("note"),
            note_provided="note" in payload,
        )
        return jsonify({
            "ok": True,
            "saved": _saved_payload(item),
            "account_id": identity.account_id,
            "generated_at": _iso_now(),
        })
    except LookupError as exc:
        code = str(exc)
        if code == "opportunity_not_found":
            return jsonify({"error": "not_found"}), 404
        return jsonify({"error": "saved_opportunity_not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()


def register_watchlist_api(app=APP):
    if "opportunity_watchlist_api" not in app.blueprints:
        app.register_blueprint(bp)


register_watchlist_api()
